"""Widgets follow `PydanticUi.update_session_data` and `clear_session_data`.

The browser keeps a keyed widget's own value unless the server pushes one
(`set_value` on the widget proto), so every re-seeded widget must push it.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

APP = "session_data_app.py"

LOADED: dict[str, Any] = {
    "sd_name": "John Doe",
    "sd_phone": "555-0101",
    "sd_role": "admin",
    "sd_plan": "pro",
    "sd_is_active": False,
    "sd_birth_date": date(1990, 5, 1),
    "sd_age": 30,
    "sd_count": 5,
}
DEFAULTS: dict[str, Any] = {
    "sd_name": "",
    "sd_phone": "",
    "sd_role": "user",
    "sd_plan": "free",
    "sd_is_active": True,
    "sd_birth_date": None,
    "sd_age": 18,
    "sd_count": 0,
}


@pytest.fixture
def loaded(run_app: Callable[[str], AppTest]) -> AppTest:
    """Render the harness, edit the name, then load the record."""
    at = run_app(APP)
    at.text_input(key="sd_name").input("Typed").run()
    at.button(key="load").click().run()
    assert not at.exception
    return at


def widgets(at: AppTest) -> dict[str, Any]:
    """Return every form widget of the harness by key."""
    elements = [
        *at.text_input,
        *at.selectbox,
        *at.checkbox,
        *at.date_input,
        *at.number_input,
    ]
    return {w.key: w for w in elements if w.key and w.key.startswith("sd_")}


def test_loaded_record_is_shown(loaded: AppTest) -> None:
    shown = {key: w.value for key, w in widgets(loaded).items()}
    assert shown == LOADED


def test_loaded_record_is_pushed_to_browser(loaded: AppTest) -> None:
    not_pushed = [key for key, w in widgets(loaded).items() if not w.proto.set_value]
    assert not_pushed == []


def test_loaded_record_survives_next_interaction(loaded: AppTest) -> None:
    loaded.run()
    shown = {key: w.value for key, w in widgets(loaded).items()}
    assert shown == LOADED
    assert "'name': 'John Doe'" in loaded.markdown[0].value


def test_cleared_form_is_pushed_to_browser(loaded: AppTest) -> None:
    loaded.button(key="clear").click().run()
    form = widgets(loaded)
    assert {key: w.value for key, w in form.items()} == DEFAULTS
    assert [key for key, w in form.items() if not w.proto.set_value] == []
