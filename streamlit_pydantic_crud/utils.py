"""Utility functions for streamlit_sql package"""

from typing import Any

import numpy as np
from sqlalchemy import Column
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute


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
    if python_type == int:
        return int(value)
    elif python_type == str:
        return str(value)
    elif python_type == float:
        return float(value)

    # Fallback: convert common numpy types to Python types
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.str_):
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
