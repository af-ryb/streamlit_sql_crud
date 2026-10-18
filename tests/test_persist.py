"""Shared dialog persistence helpers in `dialogs.persist`."""

from typing import Any
from unittest.mock import patch

from sqlalchemy import JSON, Null
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from streamlit_pydantic_crud.config_types import ManyToManyFields
from streamlit_pydantic_crud.dialogs.persist import (
    form_data_key,
    handle_save_error,
    handle_save_ok,
    json_none_as_sql_null,
    pop_m2m_data,
)
from streamlit_pydantic_crud.helpers.db_errors import format_database_error
from streamlit_pydantic_crud.state import UPDATED_KEY, data_version
from tests.conftest import Department

PERSIST = "streamlit_pydantic_crud.dialogs.persist"


def test_form_data_key() -> None:
    """The Pydantic form values live under `<prefix>_form_data`."""
    assert form_data_key("k_create") == "k_create_form_data"


def test_pop_m2m_data_moves_only_configured_fields() -> None:
    """Configured many-to-many fields move out; the rest stay in place."""
    fields: ManyToManyFields = {
        "tag_ids": {"relationship": "tags", "display_field": "name"},
        "absent": {"relationship": "other", "display_field": "name"},
    }
    data = {"name": "x", "tag_ids": [1, 2]}

    m2m = pop_m2m_data(data, fields)

    assert m2m == {"tag_ids": [1, 2]}
    assert data == {"name": "x"}


def test_handle_save_error_counts_logs_and_formats() -> None:
    """A failed save counts as a write, logs a failure and formats the error."""
    state = {UPDATED_KEY: 3}
    version = data_version()
    error = RuntimeError("boom")
    with (
        patch("streamlit_pydantic_crud.state.ss", state),
        patch(f"{PERSIST}.log") as mock_log,
        patch(f"{PERSIST}.logger") as mock_logger,
    ):
        try:
            raise error
        except RuntimeError as e:
            result = handle_save_error("UPDATE", Department, {"id": 1}, e)

    assert result == (False, format_database_error(error))
    assert state[UPDATED_KEY] == 4
    assert data_version() == version + 1
    mock_log.assert_called_once_with("UPDATE", "department", {"id": 1}, success=False)
    mock_logger.exception.assert_called_once_with("Update failed for department")


class JsonBase(DeclarativeBase):
    """Declarative base for the JSON model."""


class Blob(JsonBase):
    """Model with a JSON column mapped under another attribute name."""

    __tablename__ = "blob"

    id: Mapped[int] = mapped_column(primary_key=True)
    note: Mapped[str | None] = mapped_column()
    payload: Mapped[dict[str, Any] | None] = mapped_column("data", JSON)


def test_handle_save_ok_counts_logs_and_clears_form() -> None:
    """A committed save counts as a write, logs it and drops the form data."""
    state: dict[str, Any] = {UPDATED_KEY: 3, "k_form_data": {"a": 1}, "other": 1}
    version = data_version()
    with (
        patch("streamlit_pydantic_crud.state.ss", state),
        patch(f"{PERSIST}.log") as mock_log,
    ):
        result = handle_save_ok("CREATE", Department, "row 1", "k_form_data")

    assert result == (True, "Created successfully row 1")
    assert state == {UPDATED_KEY: 4, "other": 1}
    assert data_version() == version + 1
    mock_log.assert_called_once_with("CREATE", "department", "row 1")


def test_handle_save_ok_without_session_key() -> None:
    """Without a session key no form data is touched; UPDATE reads 'Updated'."""
    state: dict[str, Any] = {"k_form_data": {"a": 1}}
    with (
        patch("streamlit_pydantic_crud.state.ss", state),
        patch(f"{PERSIST}.log") as mock_log,
    ):
        result = handle_save_ok("UPDATE", Department, "row 1")

    assert result == (True, "Updated successfully row 1")
    assert state == {UPDATED_KEY: 1, "k_form_data": {"a": 1}}
    mock_log.assert_called_once_with("UPDATE", "department", "row 1")


def test_json_none_becomes_sql_null_only_for_json_columns() -> None:
    data = json_none_as_sql_null(Blob, {"id": 1, "note": None, "payload": None})

    assert data["id"] == 1
    assert data["note"] is None
    assert isinstance(data["payload"], Null)


def test_json_value_is_kept() -> None:
    assert json_none_as_sql_null(Blob, {"payload": {"a": 1}}) == {"payload": {"a": 1}}


def test_json_already_null_on_row_stays_none() -> None:
    """Rewriting an untouched NULL as null() would issue a needless UPDATE."""
    data = json_none_as_sql_null(Blob, {"payload": None}, Blob(payload=None))

    assert data == {"payload": None}


def test_json_cleared_on_row_becomes_sql_null() -> None:
    data = json_none_as_sql_null(Blob, {"payload": None}, Blob(payload={"a": 1}))

    assert isinstance(data["payload"], Null)
