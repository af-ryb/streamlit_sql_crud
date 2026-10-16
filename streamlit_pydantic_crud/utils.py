"""Utility functions for streamlit_sql package"""

import types
from typing import Any, Union, get_args, get_origin

import numpy as np
import pandas as pd
from sqlalchemy import JSON, Column
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute
from sqlalchemy.types import TypeDecorator, TypeEngine


def unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """Split ``X | None`` / ``Optional[X]`` into ``(X, True)``.

    Anything else, including unions of several non-None types, is returned
    unchanged as ``(tp, False)``.
    """
    if is_union(tp):
        args = get_args(tp)
        non_none = [arg for arg in args if arg is not type(None)]
        if len(args) == 2 and len(non_none) == 1:
            return non_none[0], True
    return tp, False


def is_json_type(col_type: TypeEngine[Any]) -> bool:
    """Return True for JSON-like SQLAlchemy types (``JSON``, ``JSONB``, wrappers)."""
    if isinstance(col_type, TypeDecorator):
        return is_json_type(col_type.impl_instance)
    return isinstance(col_type, JSON)


def is_union(tp: Any) -> bool:
    """Return True for both ``typing.Union[...]`` and PEP 604 ``X | Y``."""
    return get_origin(tp) in (Union, types.UnionType)


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


def tablename(model: type[DeclarativeBase]) -> str:
    """Return the model's ``__tablename__``, or its class name when it has none."""
    return getattr(model, "__tablename__", model.__name__)


def pk_column(model: type[DeclarativeBase]) -> Column:
    """Return the single primary-key column of the model.

    Composite primary keys are out of scope and raise NotImplementedError.
    """
    primary_key = model.__mapper__.primary_key
    if len(primary_key) != 1:
        msg = "composite primary keys are not supported"
        raise NotImplementedError(msg)
    return primary_key[0]


def pk_name(model: type[DeclarativeBase]) -> str:
    """Return the primary-key column name of the model."""
    return pk_column(model).key


def pk_attr(model: type[DeclarativeBase]) -> InstrumentedAttribute:
    """Return the mapped primary-key attribute, for `== x` / `.in_(...)` clauses."""
    return getattr(model, pk_name(model))


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


def convert_numpy_list_to_python(values: list, model: type[DeclarativeBase]) -> list:
    """Convert a list of potentially numpy values to Python native types

    Args:
        values: List of values to convert
        model: SQLAlchemy model class to get the primary key type from

    Returns:
        List with values converted to appropriate Python native types
    """
    return [convert_numpy_to_python(value, model) for value in values]


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
