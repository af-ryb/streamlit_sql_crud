"""Format values, labels and DataFrame columns for display.

Depends on `sa_model` and `values` only; never on Streamlit state.
"""

import math
from collections.abc import Callable, Iterable
from decimal import Decimal
from functools import cache, partial
from typing import Any

import pandas as pd
from sqlalchemy import CTE, Numeric
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum

from streamlit_pydantic_crud.sa_model import is_array_type, is_json_type
from streamlit_pydantic_crud.values import enum_value, json_to_text

"""Per-column formatter accepted by pandas ``Styler.format``."""
DfStyleFormatter = dict[Any, str | Callable[[object], str] | None]


def convert_arrow(
    columns: Iterable[KeyedColumnElement[Any]], df: pd.DataFrame
) -> pd.DataFrame:
    """Make enum, JSON and ARRAY columns of `df` displayable by Arrow, in place.

    Enums become their values, JSON indented text and arrays a joined string.
    """
    for col in columns:
        col_name = col.name
        if col_name in df.columns:
            if isinstance(col.type, SQLEnum):
                df[col_name] = df[col_name].map(enum_value)
            elif is_json_type(col.type):
                df[col_name] = df[col_name].apply(
                    lambda x: json_to_text(x) if x is not None else None
                )
            elif is_array_type(col.type):
                df[col_name] = df[col_name].apply(
                    lambda x: (
                        ", ".join(map(str, x))
                        if x is not None and isinstance(x, (list, tuple))
                        else str(x)
                        if x is not None
                        else None
                    )
                )

    return df


def numeric_formatters(cte: CTE, columns: Iterable[str]) -> DfStyleFormatter:
    """Return Styler formatters for the Numeric/Float columns of `cte` in `columns`.

    Styler otherwise shows every float with 6 decimals (50000.000000).
    """
    names = set(columns)
    return {
        col.name: partial(format_number, scale=col.type.scale)
        for col in cte.columns
        if col.name in names and isinstance(col.type, Numeric)
    }


def format_number(value: object, scale: int | None = None) -> str:
    """Format a number with `scale` decimals, or its shortest repr if None.

    Missing, infinite and non-numeric values keep their plain str().
    """
    if not isinstance(value, float | int | Decimal) or not math.isfinite(value):
        return str(value)
    if scale is not None:
        return f"{value:.{scale}f}"
    return str(value)


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
