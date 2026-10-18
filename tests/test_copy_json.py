"""Copying a row with a JSON column prefills the create form from the raw record.

The record keeps JSON as a dict, so the schema form's text area holds valid
JSON (not a JSON-encoded string). AppTest cannot rerun an open dialog, so
saving is covered by the dialog tests.
"""

import json
from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest

APP = "copy_json_app.py"
"""Seeded in row 1 by `tests/_apps/copy_json_app.py`."""
META = {"k": 1, "mixed": [1, "a", None]}


@pytest.fixture
def open_copy(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Return a callable opening the copy dialog of row 0 in a form `mode`."""

    def _open(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        at = run_app(APP)
        at.session_state["SELECT"] = [0]
        at.run()
        at.button(key="note_stsql_action_add").click().run()
        assert not at.exception, [e.message for e in at.exception]
        return at

    return _open


def test_schema_copy_prefills_valid_json(
    open_copy: Callable[[str], AppTest],
) -> None:
    at = open_copy("schema")
    text = at.text_area(key="note_create_meta").value
    assert text is not None
    assert json.loads(text) == META
    assert at.text_input(key="note_create_title").value == "first"


def test_plain_copy_prefills_columns(open_copy: Callable[[str], AppTest]) -> None:
    at = open_copy("plain")
    assert at.selectbox(key="note_create_title").value == "first"
    """Plain forms have no JSON widget: `meta` is not part of the form."""
    assert not at.text_area
