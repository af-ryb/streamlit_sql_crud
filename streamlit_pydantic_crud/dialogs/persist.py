"""Persistence helpers shared by the create, edit and delete dialogs."""

from typing import Any, Literal

from loguru import logger
from sqlalchemy.orm import DeclarativeBase, Session, selectinload
from sqlalchemy.orm.interfaces import LoaderOption
from streamlit import session_state as ss

from streamlit_pydantic_crud.config_types import ManyToManyFields
from streamlit_pydantic_crud.db_errors import format_database_error
from streamlit_pydantic_crud.logs import log
from streamlit_pydantic_crud.sa_model import pk_attr, related_model, tablename
from streamlit_pydantic_crud.state import UPDATED_KEY


def form_data_key(key_prefix: str) -> str:
    """Return the session-state key holding a dialog's Pydantic form values."""
    return f"{key_prefix}_form_data"


def m2m_load_options(
    model: type[DeclarativeBase], many_to_many_fields: ManyToManyFields
) -> list[LoaderOption]:
    """Return a ``selectinload`` option per many-to-many relationship of `model`."""
    return [
        selectinload(getattr(model, config["relationship"]))
        for config in many_to_many_fields.values()
    ]


def pop_m2m_data(
    main_data: dict[str, Any], many_to_many_fields: ManyToManyFields
) -> dict[str, Any]:
    """Move the many-to-many fields out of `main_data` and return them."""
    m2m_data = {}
    for field_name in many_to_many_fields:
        if field_name in main_data:
            m2m_data[field_name] = main_data.pop(field_name)
    return m2m_data


def load_related(
    s: Session,
    model: type[DeclarativeBase],
    relationship_name: str,
    ids: list[Any],
) -> list[Any]:
    """Load the rows with primary key in `ids` across `relationship_name`."""
    related = related_model(model, relationship_name)
    return s.query(related).filter(pk_attr(related).in_(ids)).all()


def handle_save_error(
    action: Literal["CREATE", "UPDATE", "DELETE"],
    model: type[DeclarativeBase],
    row: object,
    error: Exception,
) -> tuple[bool, str]:
    """Count the attempt, log the failed `action` and return its error message.

    Call it from an ``except`` block so the traceback is logged.
    """
    ss[UPDATED_KEY] += 1
    table_name = tablename(model)
    log(action, table_name, row, success=False)
    logger.exception(f"{action.capitalize()} failed for {table_name}")
    return False, format_database_error(error)
