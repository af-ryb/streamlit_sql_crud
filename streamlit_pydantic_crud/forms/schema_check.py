"""Check that a Pydantic schema fits the SQLAlchemy model it edits.

Kept apart from `sa_model`, a leaf module, which `helpers.typing` reaches
through `values`; importing `model_fields` there would cycle.
"""

from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase

from streamlit_pydantic_crud.helpers.sa_model import pk_name, tablename
from streamlit_pydantic_crud.helpers.typing import model_fields


def validate_schema_compatibility(
    schema: type[BaseModel], model: type[DeclarativeBase], operation: str
) -> bool:
    """Validate that Pydantic schema is compatible with the SQLAlchemy model

    Every schema field must be a column, relationship or property of the
    model; an update schema must also include the primary key.

    Args:
        schema: Pydantic schema class
        model: SQLAlchemy model class
        operation: 'create', 'update' or 'read'

    Returns:
        bool: True if compatible, False otherwise
    """
    try:
        schema_fields = model_fields(schema)
        sqlalchemy_columns = {col.name: col for col in model.__table__.columns}

        relationships = {}
        for attr_name in dir(model):
            attr = getattr(model, attr_name)
            if hasattr(attr, "property") and hasattr(attr.property, "mapper"):
                relationships[attr_name] = attr

        properties = {}
        for attr_name in dir(model):
            attr = getattr(model, attr_name)
            if isinstance(attr, property):
                properties[attr_name] = attr

        for field_name in schema_fields:
            if (
                field_name not in sqlalchemy_columns
                and field_name not in relationships
                and field_name not in properties
            ):
                table_name = tablename(model)
                logger.warning(
                    f"Field '{field_name}' in {schema.__name__} "
                    f"not found in {table_name}"
                )
                return False

        pk = pk_name(model)
        if operation == "update" and pk not in schema_fields:
            logger.warning(f"Update schema {schema.__name__} must include '{pk}' field")
            return False

        return True

    except Exception:
        """Surface the real cause instead of a misleading "not compatible"."""
        logger.exception("Error validating schema compatibility")
        raise
