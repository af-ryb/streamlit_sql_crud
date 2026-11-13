"""Copying a row prefills the create form from the stored row, not the table.

The table record holds only what the read query / `read_schema` shows; a
foreign key left out of it (the consumer's alert table) must still be copied.
"""

from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest

from tests._apps.copy_fk_models import ID_ANDROID, ID_RULE_HIGH

APP = "copy_fk_app.py"


@pytest.fixture
def open_copy(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Return a callable opening the copy dialog of row 0 in a harness `mode`."""

    def _open(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        at = run_app(APP)
        at.session_state["SELECT"] = [0]
        at.run()
        at.button(key="alert_stsql_action_add").click().run()
        assert not at.exception, [e.message for e in at.exception]
        return at

    return _open


@pytest.mark.parametrize("mode", ["schema", "columns"])
def test_schema_copy_prefills_hidden_columns(
    open_copy: Callable[[str], AppTest], mode: str
) -> None:
    at = open_copy(mode)
    assert at.selectbox(key="alert_create_template_id").value == ID_ANDROID
    assert at.text_input(key="alert_create_fact_query").value == "select 1"
    """`note` is in neither the read query's columns nor the read schema."""
    assert at.text_input(key="alert_create_note").value == "keep me"
    if mode == "schema":
        """Related rows are selected by PK, not by the names the table shows."""
        assert at.multiselect(key="alert_create_rules").value == [ID_RULE_HIGH]


@pytest.mark.parametrize("mode", ["schema_plain", "columns_plain"])
def test_plain_copy_prefills_hidden_columns(
    open_copy: Callable[[str], AppTest], mode: str
) -> None:
    at = open_copy(mode)
    """Plain forms select the option object of the stored FK value."""
    template = at.selectbox(key="alert_create_template_id").value
    assert template is not None
    assert (template.idx, template.name) == (ID_ANDROID, "Alpha_android")
    assert at.selectbox(key="alert_create_note").value == "keep me"
