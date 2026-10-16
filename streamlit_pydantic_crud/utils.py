"""Utility functions for streamlit_sql package"""

import types
from typing import Any, Union, get_args, get_origin

import numpy as np
from sqlalchemy import Column
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute


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


def is_union(tp: Any) -> bool:
    """Return True for both ``typing.Union[...]`` and PEP 604 ``X | Y``."""
    return get_origin(tp) in (Union, types.UnionType)


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
