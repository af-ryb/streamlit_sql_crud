"""Introspect SQLAlchemy models, columns and column types.

Leaf module: depends only on SQLAlchemy and `config_types`.
"""

from typing import Any, cast

from sqlalchemy import ARRAY, JSON, Column, inspect
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute, selectinload
from sqlalchemy.orm.interfaces import LoaderOption
from sqlalchemy.sql.elements import ColumnElement, KeyedColumnElement
from sqlalchemy.types import TypeDecorator, TypeEngine

from streamlit_pydantic_crud.config_types import ManyToManyFields, MappedModel


def declarative_model(model: type[MappedModel]) -> type[DeclarativeBase]:
    """Type a mapped model class as `DeclarativeBase` for the internals.

    SQLModel tables are mapped at runtime but their typing lacks `__table__`.
    """
    return cast("type[DeclarativeBase]", model)


def tablename(model: type[DeclarativeBase]) -> str:
    """Return the model's ``__tablename__``, or its class name when it has none."""
    return getattr(model, "__tablename__", model.__name__)


def pk_attr(model: type[DeclarativeBase]) -> InstrumentedAttribute:
    """Return the mapped primary-key attribute, for `== x` / `.in_(...)` clauses."""
    return getattr(model, pk_name(model))


def pk_name(model: type[DeclarativeBase]) -> str:
    """Return the primary-key column name of the model."""
    return pk_column(model).key


def pk_column(model: type[DeclarativeBase]) -> Column:
    """Return the single primary-key column of the model.

    Composite primary keys are out of scope and raise NotImplementedError.
    """
    primary_key = model.__mapper__.primary_key
    if len(primary_key) != 1:
        msg = "composite primary keys are not supported"
        raise NotImplementedError(msg)
    return primary_key[0]


def related_model(
    model: type[DeclarativeBase], relationship: str
) -> type[DeclarativeBase]:
    """Return the model on the other side of `model`'s `relationship`."""
    return getattr(model, relationship).property.mapper.class_


def m2m_load_options(
    model: type[DeclarativeBase], many_to_many_fields: ManyToManyFields
) -> list[LoaderOption]:
    """Return a ``selectinload`` option per many-to-many relationship of `model`."""
    return [
        selectinload(getattr(model, config["relationship"]))
        for config in many_to_many_fields.values()
    ]


def model_by_tablename(
    model: type[DeclarativeBase], name: str
) -> type[DeclarativeBase] | None:
    """Return the class mapped to table `name` in `model`'s registry, or None."""
    return next(
        (
            mapper.class_
            for mapper in inspect(model).registry.mappers
            if getattr(mapper.class_, "__tablename__", None) == name
        ),
        None,
    )


def foreign_key_column_names(model: type[DeclarativeBase]) -> set[str]:
    """Return the names of the model's foreign-key columns."""
    return {
        col.description
        for col in model.__table__.columns
        if col.foreign_keys and col.description
    }


def column_label(col: KeyedColumnElement[Any]) -> str:
    """Return the column's description, or its name for unlabeled (joined) ones."""
    return col.description or col.name


def safe_python_type(col: ColumnElement[Any]) -> type | None:
    """Return the column's Python type, or None when the type has none.

    A `TypeDecorator` without its own (e.g. SQLModel's `AutoString`) uses its
    impl's. `NullType` (`literal_column`, untyped `func.*`) has none.
    """
    col_type = col.type
    while True:
        try:
            py_type = col_type.python_type
        except NotImplementedError:
            py_type = object
        """SQLAlchemy 2.0 raises NotImplementedError for an unknown type, 2.1
        returns `object`; both mean the type has none of its own."""
        if py_type is not object:
            return py_type
        if not isinstance(col_type, TypeDecorator):
            return None
        col_type = col_type.impl_instance


def is_json_type(col_type: TypeEngine[Any]) -> bool:
    """Return True for JSON-like SQLAlchemy types (``JSON``, ``JSONB``, wrappers)."""
    if isinstance(col_type, TypeDecorator):
        return is_json_type(col_type.impl_instance)
    return isinstance(col_type, JSON)


def is_array_type(col_type: TypeEngine[Any]) -> bool:
    """Return True for ``ARRAY`` types, also dialect or custom ones named ARRAY.

    The name check catches types that compile to ARRAY without subclassing it.
    """
    return isinstance(col_type, ARRAY) or "ARRAY" in str(col_type).upper()
