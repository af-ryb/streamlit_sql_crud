"""Persistence helpers shared by the create, edit and delete dialogs."""

from typing import Any, Literal

from loguru import logger
from sqlalchemy import JSON, inspect, null
from sqlalchemy.orm import DeclarativeBase, Session

from streamlit_pydantic_crud.config_types import ManyToManyFields
from streamlit_pydantic_crud.helpers.db_errors import format_database_error
from streamlit_pydantic_crud.helpers.logs import log
from streamlit_pydantic_crud.helpers.sa_model import pk_attr, related_model, tablename
from streamlit_pydantic_crud.state import clear_state_keys, record_write


def form_data_key(key_prefix: str) -> str:
    """Return the session-state key holding a dialog's Pydantic form values."""
    return f"{key_prefix}_form_data"


def pop_m2m_data(
    main_data: dict[str, Any], many_to_many_fields: ManyToManyFields
) -> dict[str, Any]:
    """Move the many-to-many fields out of `main_data` and return them."""
    m2m_data = {}
    for field_name in many_to_many_fields:
        if field_name in main_data:
            m2m_data[field_name] = main_data.pop(field_name)
    return m2m_data


def json_none_as_sql_null(
    model: type[DeclarativeBase], data: dict[str, Any], row: object | None = None
) -> dict[str, Any]:
    """Return `data` with None values of JSON columns replaced by SQL NULL.

    A JSON column without ``none_as_null=True`` would store None as JSON 'null'.
    A JSON attribute already None on the edited `row` keeps None, so an
    untouched NULL causes no UPDATE.
    """
    json_attrs = {
        attr.key
        for attr in inspect(model).column_attrs
        if isinstance(attr.columns[0].type, JSON)
    }
    result = dict(data)
    for name, value in data.items():
        unchanged = row is not None and getattr(row, name, None) is None
        if value is None and name in json_attrs and not unchanged:
            result[name] = null()
    return result


def load_related(
    s: Session,
    model: type[DeclarativeBase],
    relationship_name: str,
    ids: list[Any],
) -> list[Any]:
    """Load the rows with primary key in `ids` across `relationship_name`."""
    related = related_model(model, relationship_name)
    return s.query(related).filter(pk_attr(related).in_(ids)).all()


def handle_save_ok(
    action: Literal["CREATE", "UPDATE"],
    model: type[DeclarativeBase],
    row: object,
    session_key: str | None = None,
) -> tuple[bool, str]:
    """Count the committed write, log `action`, drop the form data, report it.

    Call it after ``commit`` while the session is open, so `row` renders.
    """
    record_write()
    log(action, tablename(model), row)
    if session_key is not None:
        clear_state_keys([session_key])
    past = "Created" if action == "CREATE" else "Updated"
    return True, f"{past} successfully {row}"


def handle_save_error(
    action: Literal["CREATE", "UPDATE", "DELETE"],
    model: type[DeclarativeBase],
    row: object,
    error: Exception,
) -> tuple[bool, str]:
    """Count the attempt, log the failed `action` and return its error message.

    Call it from an ``except`` block so the traceback is logged.
    """
    record_write()
    table_name = tablename(model)
    log(action, table_name, row, success=False)
    logger.exception(f"{action.capitalize()} failed for {table_name}")
    return False, format_database_error(error)
