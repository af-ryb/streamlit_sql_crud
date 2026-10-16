"""Enum columns in SQLAlchemy mode (no Pydantic schema).

Regression: `Enum(PyEnum)` columns hold member names in `col.type.enums` while
row values are members, so editing such a row raised ValueError.
"""

from collections.abc import Callable
from enum import Enum

import pytest
from streamlit.testing.v1 import AppTest

APP = "crud_forms_app.py"


@pytest.fixture
def run_mode(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Render the forms harness app in the given scenario."""

    def _run(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        return run_app(APP)

    return _run


def test_edit_row_with_python_enum_preselects_member(
    run_mode: Callable[[str], AppTest],
) -> None:
    """Editing a row with an Enum(PyEnum) value renders with it selected."""
    at = run_mode("fields_row")

    assert not at.exception
    status = at.selectbox(key="r_status")
    assert status.label == "Status"
    assert isinstance(status.value, Enum)
    assert status.value.name == "ACTIVE"
    assert "VAL_r_status=<Status.ACTIVE: 'active'>" in [m.value for m in at.markdown]


def test_string_enum_column_preselects_value(
    run_mode: Callable[[str], AppTest],
) -> None:
    """A plain Enum('low', 'high') column uses the column name and row value."""
    at = run_mode("fields_row")

    priority = at.selectbox(key="r_priority")
    assert priority.label == "Priority"
    assert priority.value == "high"


def test_update_saves_selected_enum_member(
    run_mode: Callable[[str], AppTest],
) -> None:
    """Changing the enum in the update form persists the new member."""
    at = run_mode("update")
    assert not at.exception

    status = at.selectbox(key="t_update_status")
    current = status.value
    assert isinstance(current, Enum)
    status.select(type(current)["INACTIVE"])
    at.button[0].click().run()

    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert "DB_STATUS=<Status.INACTIVE: 'inactive'>" in texts
