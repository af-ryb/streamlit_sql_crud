"""Coerce values between the database, DataFrames and Streamlit widgets.

Leaf module: depends on numpy/pandas and `sa_model` only.
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import DeclarativeBase

from streamlit_pydantic_crud.sa_model import pk_column


def enum_value(value: Any) -> Any:
    """Return ``value.value`` for an enum member, else `value` unchanged."""
    return value.value if isinstance(value, Enum) else value


def json_to_text(value: Any) -> str:
    """Render a JSON value as text: dicts and lists indented, others via str()."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    return str(value)


def to_list(value: Any) -> list:
    """Coerce a value into a list: None → [], a PG array literal is parsed.

    Lists and tuples are copied; any other value becomes a one-item list.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        return parse_pg_array(value)
    return [value]


def parse_pg_array(value: str) -> list[str]:
    """Parse a PostgreSQL array literal (``{a,"b,c"}``) into a list of strings.

    Braces are optional, so ``a, b`` also works. Quoted items keep commas,
    spaces and backslash-escaped characters; unquoted items are stripped and
    empty ones dropped. Nested arrays and NULL are not interpreted.
    """
    text = value.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]

    items: list[str] = []
    current: list[str] = []
    quoted = in_quotes = escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            in_quotes = not in_quotes
            quoted = True
        elif char == "," and not in_quotes:
            _append_item(items, current, quoted)
            current, quoted = [], False
        elif in_quotes or not char.isspace() or (current and not quoted):
            current.append(char)
    _append_item(items, current, quoted)
    return items


def _append_item(items: list[str], chars: list[str], quoted: bool) -> None:
    """Append a parsed array item; unquoted items are stripped, empty dropped."""
    item = "".join(chars)
    if not quoted:
        item = item.strip()
    if quoted or item:
        items.append(item)


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


def keep_unchanged_datetime(new: Any, original: Any) -> Any:
    """Return `original` when the widget value `new` is it at minute precision.

    `st.datetime_input` drops seconds, microseconds and tzinfo, so an untouched
    widget must not overwrite the stored value with that truncated copy.
    """
    if not isinstance(new, datetime) or not isinstance(original, datetime):
        return new
    truncated = original.replace(second=0, microsecond=0, tzinfo=None)
    return original if new == truncated else new


def convert_numpy_list_to_python(values: list, model: type[DeclarativeBase]) -> list:
    """Convert a list of potentially numpy values to Python native types

    Args:
        values: List of values to convert
        model: SQLAlchemy model class to get the primary key type from

    Returns:
        List with values converted to appropriate Python native types
    """
    return [convert_numpy_to_python(value, model) for value in values]


def convert_numpy_to_python(value: Any, model: type[DeclarativeBase]) -> Any:
    """Convert numpy types to Python native types based on SQLAlchemy model primary key type

    Args:
        value: The value to convert (potentially numpy type)
        model: SQLAlchemy model class to get the primary key type from

    Returns:
        The value converted to appropriate Python native type
    """
    if not isinstance(value, (np.integer, np.floating, np.str_)):
        return value

    # Get the primary key column type from the model
    python_type = pk_column(model).type.python_type
    if python_type is int:
        return int(value)
    if python_type is str:
        return str(value)
    if python_type is float:
        return float(value)

    # Fallback: convert common numpy types to Python types
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.str_):
        return str(value)

    return value


def row_to_python(row: pd.Series) -> dict[str, Any]:
    """Return a DataFrame row as a dict of plain Python values.

    NaN, NaT and pd.NA become None, numpy scalars and arrays become Python
    scalars and lists, so a copied row never prefills "nan".
    """
    return {str(name): cell_to_python(value) for name, value in row.items()}


def cell_to_python(value: Any) -> Any:
    """Convert one DataFrame cell to a plain Python value (see row_to_python)."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if not pd.api.types.is_scalar(value):
        return value
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value
