from datetime import date, datetime
from decimal import Decimal
from typing import Any

import streamlit as st
from sqlalchemy import ARRAY, Numeric
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum
from streamlit_datalist import stDatalist

from streamlit_pydantic_crud.filters import ExistingData, FkOpt
from streamlit_pydantic_crud.lib import get_pretty_name
from streamlit_pydantic_crud.utils import parse_pg_array


class InputFields:
    """Generate Streamlit input widgets for SQLAlchemy model fields.

    Automatically detects field types and creates appropriate inputs:
    - Enum fields: selectbox
    - String fields with few unique values: selectbox (String(Enum) style)
    - Array[Enum] fields: multiselect
    - Regular string fields: text input with datalist
    - Foreign keys: selectbox with related records
    - Numbers, dates, booleans: appropriate input widgets
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

    def input_fk(self, col_name: str, value: int | None) -> int | None:
        key = f"{self.key_prefix}_{col_name}"
        opts = self.existing_data.fk[col_name]

        index = next((i for i, opt in enumerate(opts) if opt.idx == value), None)
        input_value = st.selectbox(
            get_pretty_name(col_name),
            options=opts,
            format_func=lambda opt: opt.name,
            index=index,
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

        return st.selectbox(
            get_pretty_name(col_name),
            opts,
            index=index,
            format_func=lambda opt: opt.name if enum_class else str(opt),
            key=f"{self.key_prefix}_{col_name}",
        )

    def input_str_enum(self, col_name: str, value=None) -> str | None:
        """Handle string columns that should be treated as enums using selectbox."""
        key = f"{self.key_prefix}_{col_name}"
        pretty_name = get_pretty_name(col_name)

        # Get available options from existing data
        opts = list(self.existing_data.text[col_name])

        # Find current value index
        index = None
        if value and value in opts:
            index = opts.index(value)
        elif value and value not in opts:
            # If current value is not in options, add it
            opts.append(value)
            index = len(opts) - 1

        input_value = st.selectbox(
            pretty_name,
            options=opts,
            index=index,
            key=key,
            help=f"Select from {len(opts)} available options",
        )
        return input_value

    def is_string_enum_candidate(self, col_name: str) -> bool:
        """Determine if a string column should be treated as an enum based on unique value count."""
        opts = list(self.existing_data.text[col_name])
        # Treat as enum if there are threshold or fewer unique values
        return len(opts) <= self.string_enum_threshold and len(opts) > 0

    def input_str(self, col_name: str, value: str | None = None) -> str | None:
        """Render a free-text datalist input; return None when left empty."""
        key = f"{self.key_prefix}_{col_name}"
        val_index, opts = self.get_col_str_opts(col_name, value)
        input_value = stDatalist(
            get_pretty_name(col_name),
            list(opts),
            index=val_index,  # ty: ignore[invalid-argument-type]
            key=key,
        )
        if input_value is None or input_value == "":
            return None
        return str(input_value)

    @staticmethod
    def coerce_decimal(value: float | int | None, step: float | None) -> Decimal | None:
        """Convert a numeric input to Decimal, preserving 0 and quantizing.

        Returns None only when value is None, so a literal 0 is kept.
        """
        if value is None:
            return None
        value_dec = Decimal(str(value))
        if step:
            value_dec = value_dec.quantize(Decimal(str(step)))
        return value_dec

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
        key = f"{self.key_prefix}_{col_name}"
        if nullable:
            if key not in st.session_state:
                st.session_state[key] = value
            value = None
        return st.number_input(
            get_pretty_name(col_name), value=value, step=step, key=key
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

        return self.coerce_decimal(input_value, step)

    def input_array(self, col_name: str, col_type, col_value=None) -> list[Any]:
        """Handle ARRAY column input with multiselect"""
        pretty_name = get_pretty_name(col_name)

        # Convert current value to list
        current_values = []
        if col_value is not None:
            if isinstance(col_value, (list, tuple)):
                current_values = list(col_value)
            elif isinstance(col_value, str):
                current_values = parse_pg_array(col_value)

        # Get existing values for options (if available)
        existing_values = self.existing_data.text.get(col_name, set())
        options = list(existing_values) if existing_values else []

        # Add current values to options if not already present
        for val in current_values:
            if val not in options:
                options.append(val)

        # Check if this is an ARRAY of ENUM type
        enum_options = []
        if hasattr(col_type, "item_type") and isinstance(col_type.item_type, SQLEnum):
            enum_options = list(col_type.item_type.enums)
            options.extend([opt for opt in enum_options if opt not in options])

        # Multiselect input with accept_new_options for flexibility
        selected_values = st.multiselect(
            pretty_name,
            options=options,
            default=current_values,
            accept_new_options=True,
            key=f"{self.key_prefix}_{col_name}",
            help="Select existing options or type new ones"
            if not enum_options
            else f"Select from: {', '.join(enum_options)}",
        )

        return selected_values

    def get_input_value(self, col: KeyedColumnElement, col_value) -> Any:
        col_name = col.description
        if col_name is None:
            msg = "Column has no name; cannot build an input for it"
            raise ValueError(msg)
        pretty_name = get_pretty_name(col_name)
        key = f"{self.key_prefix}_{col_name}"

        if col.primary_key:
            input_value = col_value
        elif len(col.foreign_keys) > 0:
            input_value = self.input_fk(col_name, col_value)
        elif isinstance(col.type, ARRAY):
            input_value = self.input_array(col_name, col.type, col_value)
        elif "ARRAY" in str(col.type).upper():
            # Fallback for ARRAY types that don't match isinstance check
            input_value = self.input_array(col_name, col.type, col_value)
        elif isinstance(col.type, SQLEnum):
            input_value = self.input_enum(col_name, col.type, col_value)
        elif col.type.python_type is str:
            # Check if string column should be treated as enum
            if self.is_string_enum_candidate(col_name):
                input_value = self.input_str_enum(col_name, col_value)
            else:
                input_value = self.input_str(col_name, col_value)
        elif col.type.python_type is int:
            input_value = self.input_number(col_name, col_value, 1, col.nullable)
        elif col.type.python_type is float:
            input_value = self.input_number(col_name, col_value, 0.1, col.nullable)
        elif isinstance(col.type, Numeric):
            scale = col.type.scale
            input_value = self.input_numeric(col_name, scale, col_value, col.nullable)
        elif col.type.python_type is datetime:
            input_value = st.datetime_input(pretty_name, value=col_value, key=key)
        elif col.type.python_type is date:
            input_value = st.date_input(pretty_name, value=col_value, key=key)
        elif col.type.python_type is bool:
            input_value = st.checkbox(pretty_name, value=col_value, key=key)
        else:
            input_value = None

        return input_value
