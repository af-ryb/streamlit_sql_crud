"""Plain (no-schema) form widgets, one per SQLAlchemy column.

Every widget seeds its session state (`seed_widget_state`) and gets no
`value` / `index` / `default`, like the Pydantic renderers in `forms.pydantic`.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Final

import streamlit as st
from sqlalchemy import JSON, Float, Numeric
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum

from streamlit_pydantic_crud.config_types import FkOpt
from streamlit_pydantic_crud.forms.options import ExistingData
from streamlit_pydantic_crud.forms.pydantic.option_resolve import known_defaults
from streamlit_pydantic_crud.forms.pydantic.widgets import (
    nullable_number_input,
    render_checkbox,
    render_date_input,
    render_json_text_area,
    seed_widget_state,
    seeded_index,
)
from streamlit_pydantic_crud.helpers.display import get_pretty_name
from streamlit_pydantic_crud.helpers.sa_model import (
    column_label,
    is_array_type,
    safe_python_type,
)
from streamlit_pydantic_crud.helpers.typing import enum_member
from streamlit_pydantic_crud.helpers.values import (
    coerce_decimal,
    keep_unchanged_datetime,
    to_list,
)
from streamlit_pydantic_crud.state import clear_state_keys

DATETIME_YEARS: Final = 10
"""Years the datetime picker reaches before and after the value, as Streamlit."""

JSON_HELP: Final = "JSON, e.g. an object or a list"

NO_INPUT: Final = object()
"""Returned for a column without a value to save; callers leave it unchanged."""


class InputFields:
    """Generate Streamlit input widgets for SQLAlchemy model fields.

    Automatically detects field types and creates appropriate inputs:
    - Enum fields: selectbox
    - String fields: selectbox of stored values that also takes a new value
    - Array fields: multiselect (Array[Enum]: its members, shown by name)
    - Foreign keys: selectbox with related records
    - JSON fields: text area holding the value as JSON, parsed on save
    - Numbers, dates, booleans: appropriate input widgets

    `errors` maps a column to the message of its invalid input.
    """

    def __init__(
        self,
        model: type[DeclarativeBase],
        key_prefix: str,
        default_values: dict,
        existing_data: ExistingData,
        string_enum_threshold: int = 10,
    ) -> None:
        """Initialize InputFields.

        Args:
            model: SQLAlchemy model class
            key_prefix: Prefix for widget keys to avoid conflicts
            default_values: Default values for fields
            existing_data: Existing data helper for options
            string_enum_threshold: Max unique values for string field to be treated as enum
        """
        self.model = model
        self.key_prefix = key_prefix
        self.default_values = default_values
        self.existing_data = existing_data
        self.string_enum_threshold = string_enum_threshold
        self.errors: dict[str, str] = {}

    def input_fk(self, col_name: str, value: int | None) -> int | None:
        key = f"{self.key_prefix}_{col_name}"
        opts = self.existing_data.fk[col_name]

        index = next((i for i, opt in enumerate(opts) if opt.idx == value), None)
        seed_widget_state(key, None if index is None else opts[index])
        input_value = st.selectbox(
            get_pretty_name(col_name),
            options=opts,
            format_func=lambda opt: opt.name,
            index=seeded_index(index),
            key=key,
        )
        if not input_value:
            return None
        if not isinstance(input_value, FkOpt):
            msg = f"Expected an FkOpt option for {col_name}, got {input_value!r}"
            raise TypeError(msg)
        return input_value.idx

    def get_col_str_opts(
        self, col_name: str, value: str | None
    ) -> tuple[int | None, list[str]]:
        opts = list(self.existing_data.text[col_name])
        if value is None:
            return None, opts

        try:
            val_index = opts.index(value)
            return val_index, opts
        except ValueError:
            opts.append(value)
            val_index = len(opts) - 1
            return val_index, opts

    def input_enum(
        self, col_name: str, col_enum: SQLEnum, col_value: object = None
    ) -> object:
        """Render a selectbox for an Enum column and return the chosen option.

        `Enum(PyEnum)` columns offer (and return) members; string enums offer
        their literal values. A stored member name is mapped back to its member.
        """
        enum_class = col_enum.enum_class
        opts: list = list(enum_class) if enum_class else list(col_enum.enums)

        if enum_class and isinstance(col_value, str):
            col_value = enum_class.__members__.get(col_value, col_value)
        index = opts.index(col_value) if col_value in opts else None
        key = f"{self.key_prefix}_{col_name}"
        seed_widget_state(key, None if index is None else opts[index])

        return st.selectbox(
            get_pretty_name(col_name),
            opts,
            index=seeded_index(index),
            format_func=lambda opt: opt.name if enum_class else str(opt),
            key=key,
        )

    def input_str_enum(
        self, col_name: str, value: str | None = None, nullable: bool = True
    ) -> str | None:
        """Render a short string column: its few stored values, or a new one.

        Unlike a real Enum the column takes any string, so typing is allowed.
        """
        count = len(self.existing_data.text[col_name])
        return self.select_or_type_str(
            col_name,
            value,
            f"Select one of {count} values or type a new one",
            nullable,
        )

    def is_string_enum_candidate(self, col_name: str) -> bool:
        """Determine if a string column should be treated as an enum based on unique value count."""
        opts = list(self.existing_data.text[col_name])
        # Treat as enum if there are threshold or fewer unique values
        return len(opts) <= self.string_enum_threshold and len(opts) > 0

    def input_str(
        self, col_name: str, value: str | None = None, nullable: bool = True
    ) -> str | None:
        """Render a free-text input suggesting stored values; None when empty."""
        return self.select_or_type_str(
            col_name, value, "Select a stored value or type a new one", nullable
        )

    def select_or_type_str(
        self, col_name: str, value: str | None, help_text: str, nullable: bool
    ) -> str | None:
        """Render a selectbox of stored values that accepts a typed new one.

        Returns None when nothing is selected or the text is empty. A nullable
        column passes no index (not even 0), which keeps it clearable.
        """
        key = f"{self.key_prefix}_{col_name}"
        val_index, opts = self.get_col_str_opts(col_name, value)
        seed_widget_state(key, value)
        input_value = st.selectbox(
            get_pretty_name(col_name),
            options=opts,
            index=None if nullable else seeded_index(val_index),
            key=key,
            help=help_text,
            accept_new_options=True,
        )
        if input_value is None or input_value == "":
            return None
        return str(input_value)

    def input_number(
        self,
        col_name: str,
        value: float | None,
        step: float | None,
        nullable: bool = False,
    ) -> float | None:
        """Render an int/float number input; a nullable one can be emptied.

        A widget created with a value refills a cleared field on blur, so a
        nullable column seeds its state and starts with `value=None` instead.
        """
        return nullable_number_input(
            get_pretty_name(col_name),
            value,
            f"{self.key_prefix}_{col_name}",
            nullable=nullable,
            step=step,
        )

    def input_numeric(
        self,
        col_name: str,
        scale: int | None,
        value: object = None,
        nullable: bool = False,
    ) -> Decimal | None:
        """Render a number input for a Numeric column and return a Decimal."""
        step = None
        if scale:
            step = 10 ** (scale * -1)

        value_float = float(str(value)) if value is not None else None
        input_value = self.input_number(col_name, value_float, step, nullable)

        return coerce_decimal(input_value, step)

    def input_array(self, col_name: str, col_type, col_value=None) -> list[Any]:
        """Render a multiselect for an ARRAY column and return the selection.

        Typed new items are accepted, except for an ARRAY of Enum.
        """
        item_type = getattr(col_type, "item_type", None)
        if isinstance(item_type, SQLEnum):
            return self.input_enum_array(col_name, item_type, col_value)

        """Only lists, tuples and PG array literals preselect values; any other
        scalar gives none (to_list would wrap it)."""
        current_values = array_items(col_value)

        existing_values = self.existing_data.text.get(col_name, set())
        options = list(existing_values) if existing_values else []
        for val in current_values:
            if val not in options:
                options.append(val)

        key = f"{self.key_prefix}_{col_name}"
        seed_widget_state(key, current_values)
        return st.multiselect(
            get_pretty_name(col_name),
            options=options,
            accept_new_options=True,
            key=key,
            help="Select existing options or type new ones",
        )

    def input_enum_array(
        self, col_name: str, item_enum: SQLEnum, col_value: object = None
    ) -> list[Any]:
        """Render a multiselect for an ARRAY of Enum, labelled by name.

        `Enum(PyEnum)` items offer (and return) members, string enums their
        literal values; stored names, values and members all select the option.
        """
        enum_class = item_enum.enum_class
        options: list = list(enum_class) if enum_class else list(item_enum.enums)
        label = get_pretty_name(col_name)

        items = array_items(col_value)
        if enum_class:
            items = [stored_enum_member(item, enum_class) for item in items]
        key = f"{self.key_prefix}_{col_name}"
        seed_widget_state(key, known_defaults(items, options, label))
        return st.multiselect(
            label,
            options=options,
            format_func=lambda opt: opt.name if enum_class else str(opt),
            key=key,
            help=f"Select from: {', '.join(item_enum.enums)}",
        )

    def input_datetime(self, col_name: str, value: datetime | None) -> Any:
        """Render a datetime input; an untouched one returns `value` unchanged.

        "now" stands for "no default"; the bounds span the stored value and now.
        """
        key = f"{self.key_prefix}_{col_name}"
        label = get_pretty_name(col_name)
        if not isinstance(value, datetime):
            seed_widget_state(key, None)
            return st.datetime_input(label, value=None, key=key)
        shown = value.replace(second=0, microsecond=0, tzinfo=None)
        seed_widget_state(key, shown)
        years = sorted((shown.year, datetime.now().year))
        input_value = st.datetime_input(
            label,
            value="now",
            min_value=date(max(years[0] - DATETIME_YEARS, date.min.year), 1, 1),
            max_value=date(min(years[1] + DATETIME_YEARS, date.max.year), 12, 31),
            key=key,
        )
        return keep_unchanged_datetime(input_value, value)

    def input_json(
        self, col_name: str, value: object = None, nullable: bool = True
    ) -> Any:
        """Render a JSON text area and return the parsed value.

        Returns `NO_INPUT` for an invalid input, recording it in `errors`.
        """
        label = get_pretty_name(col_name)
        text = render_json_text_area(
            label,
            {"help": JSON_HELP},
            json_source(value) or None,
            f"{self.key_prefix}_{col_name}",
        )
        self.errors.pop(col_name, None)
        try:
            return parse_json_input(text, value, nullable)
        except ValueError as error:
            self.errors[col_name] = f"{label}: {error}"
            return NO_INPUT

    def show_errors(self) -> bool:
        """Show the message of every invalid input; True when there is one."""
        for message in self.errors.values():
            st.error(message)
        return bool(self.errors)

    def get_input_value(self, col: KeyedColumnElement, col_value) -> Any:
        """Render the widget for `col` and return its value.

        Returns `NO_INPUT` for a type without a widget or without a value to
        save (an invalid or an empty, unchanged JSON input).
        """
        col_name = column_label(col)
        pretty_name = get_pretty_name(col_name)
        key = f"{self.key_prefix}_{col_name}"
        py_type = safe_python_type(col)

        if col.primary_key:
            input_value = col_value
        elif len(col.foreign_keys) > 0:
            input_value = self.input_fk(col_name, col_value)
        elif is_array_type(col.type):
            input_value = self.input_array(col_name, col.type, col_value)
        elif isinstance(col.type, JSON):
            input_value = self.input_json(col_name, col_value, bool(col.nullable))
        elif isinstance(col.type, SQLEnum):
            input_value = self.input_enum(col_name, col.type, col_value)
        elif py_type is str:
            if self.is_string_enum_candidate(col_name):
                input_value = self.input_str_enum(col_name, col_value, col.nullable)
            else:
                input_value = self.input_str(col_name, col_value, col.nullable)
        elif py_type is int:
            input_value = self.input_number(col_name, col_value, 1, col.nullable)
        elif py_type is float:
            input_value = self.input_number(col_name, col_value, 0.1, col.nullable)
        elif isinstance(col.type, Numeric | Float):
            """SQLAlchemy 2.1 no longer derives Float from Numeric."""
            scale = col.type.scale
            input_value = self.input_numeric(col_name, scale, col_value, col.nullable)
        elif py_type is datetime:
            input_value = self.input_datetime(col_name, col_value)
        elif py_type is date:
            input_value = render_date_input(pretty_name, {}, col_value, key)
        elif py_type is bool:
            input_value = render_checkbox(pretty_name, {}, col_value, key)
        else:
            input_value = NO_INPUT

        return input_value

    def reset_state(self) -> None:
        """Drop the widget values of every model column from session state.

        The next render then re-seeds each widget from the value it is given.
        """
        clear_state_keys(
            f"{self.key_prefix}_{column_label(col)}"
            for col in self.model.__table__.columns
        )


def parse_json_input(text: str | None, stored: object, nullable: bool) -> Any:
    """Return the value of a JSON text area seeded with `json_source(stored)`.

    The same JSON gives `stored` itself, nothing typed without a stored value
    `NO_INPUT`; raises ValueError for invalid JSON or a missing required value.
    """
    typed = (text or "").strip()
    if stored is None and not typed:
        return NO_INPUT
    if typed == json_source(stored):
        return stored
    try:
        parsed = json.loads(typed) if typed else None
    except json.JSONDecodeError as error:
        msg = f"invalid JSON ({error.msg}, line {error.lineno} column {error.colno})"
        raise ValueError(msg) from error
    if parsed is None and not nullable:
        msg = "a JSON value is required"
        raise ValueError(msg)
    """Compared as text: Python's == would take 1 for true."""
    return stored if json_source(parsed) == json_source(stored) else parsed


def json_source(value: object) -> str:
    """Return `value` as indented JSON text, empty for None.

    Unlike `json_to_text`, scalars are JSON too (a string is quoted).
    """
    return "" if value is None else json.dumps(value, indent=2, default=str)


def array_items(value: object) -> list[Any]:
    """Return the items of a stored array: a list, tuple or PG array literal."""
    return to_list(value) if isinstance(value, (list, tuple, str)) else []


def stored_enum_member(item: object, enum_class: type[Enum]) -> object:
    """Return the member a stored array item stands for, else the item.

    The database stores member names, so a name wins over an equal value.
    """
    if isinstance(item, str) and item in enum_class.__members__:
        return enum_class.__members__[item]
    member = enum_member(item, enum_class)
    return item if member is None else member
