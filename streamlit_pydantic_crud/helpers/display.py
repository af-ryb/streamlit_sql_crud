"""Format values, labels and table columns for display.

Depends on `sa_model` and `values` only; never on Streamlit state.
"""

from collections.abc import Callable, Iterable
from datetime import date, time, timedelta
from decimal import Decimal
from enum import Enum
from functools import cache
from typing import Any, Literal

import streamlit as st
from sqlalchemy import CTE, Float, Numeric
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum
from sqlalchemy.types import TypeEngine
from streamlit.elements.lib.column_types import ColumnConfig

from streamlit_pydantic_crud.helpers.sa_model import is_array_type, is_json_type
from streamlit_pydantic_crud.helpers.values import enum_value, json_to_text, to_list

"""Per-column formatter accepted by pandas ``Styler.format``."""
DfStyleFormatter = dict[Any, str | Callable[[object], str] | None]
"""How a column's values are displayed, decided by its SQLAlchemy type."""
ColumnKind = Literal["enum", "json", "array"]
"""Item types a list cell shows as they are; any other item becomes str()."""
PLAIN_ITEM_TYPES = (str, int, float, Decimal, date, time, timedelta)


def display_records(
    columns: Iterable[KeyedColumnElement[Any]], records: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return copies of `records` with every value ready for ``st.dataframe``.

    A key matching an enum, JSON or ARRAY column of `columns` is converted by
    that type: enum → value, JSON → text, ARRAY → list of (enum) values; a PG
    array literal string is parsed. Any other value (other column types, or a
    key without a column, like a ``read_schema`` ``@property``) is converted by
    its own type: Enum → value, list → list of `display_item`. Decimal, dates
    and None stay unchanged.
    """
    kinds = {
        col.name: kind for col in columns if (kind := column_kind(col.type)) is not None
    }
    return [
        {key: display_cell(kinds.get(key), value) for key, value in record.items()}
        for record in records
    ]


def display_cell(kind: ColumnKind | None, value: Any) -> Any:
    """Convert one cell `value` for display, by its column `kind` if known."""
    if value is None:
        return None
    if kind == "json":
        return json_to_text(value)
    if kind == "array":
        return [enum_value(item) for item in to_list(value)]
    if isinstance(value, list | tuple):
        return [display_item(item) for item in value]
    return enum_value(value)


def display_item(item: Any) -> Any:
    """Return a list item displayable by Arrow: enum value, plain scalar or str().

    ORM objects of a loaded relationship, nested dicts and the like become str().
    """
    if item is None or isinstance(item, PLAIN_ITEM_TYPES):
        return item
    if isinstance(item, Enum):
        return item.value
    return str(item)


def column_kind(col_type: TypeEngine[Any]) -> ColumnKind | None:
    """Return the display kind of a column type, None when values pass as is."""
    if isinstance(col_type, SQLEnum):
        return "enum"
    if is_json_type(col_type):
        return "json"
    if is_array_type(col_type):
        return "array"
    return None


def column_configs(cte: CTE, columns: Iterable[str]) -> dict[str, ColumnConfig]:
    """Return default ``st.dataframe`` column configs for the `cte` `columns`.

    Numeric/Float get a number format by scale, ARRAY columns a list column.
    """
    names = set(columns)
    configs: dict[str, ColumnConfig] = {}
    for col in cte.columns:
        if col.name not in names:
            continue
        if isinstance(col.type, Numeric | Float):
            """SQLAlchemy 2.1 no longer derives Float from Numeric."""
            configs[col.name] = st.column_config.NumberColumn(
                format=number_format(getattr(col.type, "scale", None))
            )
        elif is_array_type(col.type):
            configs[col.name] = st.column_config.ListColumn()
    return configs


def number_format(scale: int | None) -> str:
    """Return a ``NumberColumn`` format: `scale` decimals, else the shortest repr.

    Matches the former Styler formatter (``f"{v:.2f}"`` / ``str(v)``): the
    browser's ``%g`` has no precision limit, while ``plain`` shows float noise
    (3.1415900000000003) and the default rounds to 4 decimals.
    """
    return "%g" if scale is None else f"%.{scale}f"


def display_value(value: Any) -> str:
    """Return the label of a filter option: the enum value or str()."""
    return str(enum_value(value))


def field_label(field_name: str, description: str | None) -> str:
    """Return a form field label: its description, else the pretty field name."""
    return str(description) if description else get_pretty_name(field_name)


@cache
def get_pretty_name(name: str) -> str:
    """Return `name` title-cased with underscores as spaces (``First Name``)."""
    return " ".join(name.split("_")).title()
