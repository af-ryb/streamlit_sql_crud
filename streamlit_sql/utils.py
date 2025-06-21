"""Utility functions for streamlit_sql package"""

from sqlalchemy.orm import DeclarativeBase


def convert_numpy_to_python(value, model: type[DeclarativeBase]):
    """Convert numpy types to Python native types based on SQLAlchemy model primary key type
    
    Args:
        value: The value to convert (potentially numpy type)
        model: SQLAlchemy model class to get the primary key type from
        
    Returns:
        The value converted to appropriate Python native type
    """
    import numpy as np
    
    if not isinstance(value, (np.integer, np.floating, np.str_)):
        return value
    
    # Get the primary key column type from the model
    id_column = model.__table__.columns.get('id')
    if id_column is not None:
        python_type = id_column.type.python_type
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
