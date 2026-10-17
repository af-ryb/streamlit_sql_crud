"""Reopening an edit/create dialog must drop unsaved values of the last one.

The dialog reruns the app when dismissed, and the run reopening it re-seeds
the form, so neither browser nor session state keeps the stale values.
"""

from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest

APP = "dialog_reset_app.py"
UPDATE_MODES = ["update", "update_schema"]
CREATE_MODES = ["create", "create_schema"]


@pytest.fixture
def open_dialog(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Return a callable rendering the harness in `mode` with the dialog open."""

    def _open(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        at = run_app(APP)
        at.button(key="open").click().run()
        assert not at.exception
        return at

    return _open


def edit_and_reopen(at: AppTest, prefix: str) -> AppTest:
    """Change widgets without saving, then open the dialog again in one run.

    The client still sends the stale widget values on the reopening run.
    """
    at.number_input(key=f"{prefix}_count").set_value(555)
    at.checkbox(key=f"{prefix}_done").check()
    at.number_input(key=f"{prefix}_qty").set_value(99)
    at.button(key="open").click().run()
    assert not at.exception
    return at


@pytest.mark.parametrize("mode", UPDATE_MODES)
def test_reopened_edit_dialog_shows_db_values(
    open_dialog: Callable[[str], AppTest], mode: str
) -> None:
    at = edit_and_reopen(open_dialog(mode), "t_update")
    assert at.number_input(key="t_update_count").value == 7
    assert at.checkbox(key="t_update_done").value is False
    assert at.number_input(key="t_update_qty").value == 3
    assert "DB_COUNT=7" in markdown(at)


@pytest.mark.parametrize("mode", CREATE_MODES)
def test_reopened_create_dialog_starts_from_defaults(
    open_dialog: Callable[[str], AppTest], mode: str
) -> None:
    at = open_dialog(mode)
    count = at.number_input(key="t_create_count").value
    qty = at.number_input(key="t_create_qty").value
    at = edit_and_reopen(at, "t_create")
    assert at.number_input(key="t_create_count").value == count
    assert at.checkbox(key="t_create_done").value is False
    assert at.number_input(key="t_create_qty").value == qty


def test_reopened_copy_dialog_shows_copied_values(
    open_dialog: Callable[[str], AppTest],
) -> None:
    at = edit_and_reopen(open_dialog("copy_schema"), "t_create")
    assert at.number_input(key="t_create_count").value == 7
    assert at.number_input(key="t_create_qty").value == 3


def test_open_dialog_keeps_values_after_validation_error(
    open_dialog: Callable[[str], AppTest],
) -> None:
    at = open_dialog("update_schema")
    at.number_input(key="t_update_count").set_value(5000)
    at.button(key="FormSubmitter:t_update_form-Save").click().run()
    assert not at.exception
    assert at.error
    assert at.number_input(key="t_update_count").value == 5000
    assert "DB_COUNT=7" in markdown(at)


def test_edit_dialog_saves_changes(open_dialog: Callable[[str], AppTest]) -> None:
    at = open_dialog("update")
    at.number_input(key="t_update_count").set_value(42)
    at.button(key="FormSubmitter:update_model_form_Item_t_update-Save").click()
    at.run()
    assert not at.exception
    assert "DB_COUNT=42" in markdown(at)


@pytest.mark.parametrize("mode", [*UPDATE_MODES, *CREATE_MODES])
def test_dismissing_dialog_reruns_app(
    open_dialog: Callable[[str], AppTest], mode: str
) -> None:
    """A dismiss rerun drops the widget state the browser keeps for the dialog.

    Streamlit gives the dialog block an id only when `on_dismiss` reruns.
    """
    at = open_dialog(mode)
    (dialog,) = at.get("dialog")
    assert dialog.proto.dialog.id


def markdown(at: AppTest) -> str:
    """Return all markdown text of the app joined by newlines."""
    return "\n".join(m.value for m in at.markdown)
