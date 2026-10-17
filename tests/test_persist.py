"""Shared dialog persistence helpers in `dialogs.persist`."""

from unittest.mock import patch

from streamlit_pydantic_crud.config_types import ManyToManyFields
from streamlit_pydantic_crud.dialogs.persist import (
    form_data_key,
    handle_save_error,
    pop_m2m_data,
)
from streamlit_pydantic_crud.helpers.db_errors import format_database_error
from streamlit_pydantic_crud.state import UPDATED_KEY
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
    """A failed save bumps the counter, logs a failure and formats the error."""
    state = {UPDATED_KEY: 3}
    error = RuntimeError("boom")
    with (
        patch(f"{PERSIST}.ss", state),
        patch(f"{PERSIST}.log") as mock_log,
        patch(f"{PERSIST}.logger") as mock_logger,
    ):
        try:
            raise error
        except RuntimeError as e:
            result = handle_save_error("UPDATE", Department, {"id": 1}, e)

    assert result == (False, format_database_error(error))
    assert state[UPDATED_KEY] == 4
    mock_log.assert_called_once_with("UPDATE", "department", {"id": 1}, success=False)
    mock_logger.exception.assert_called_once_with("Update failed for department")
