"""The success/error banner shows once, not on every rerun (#8)."""

import os
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.state import UiState, state_key_for
from tests.conftest import APP_DIR


def test_notification_clears_after_one_render(tmp_path: Path) -> None:
    """A pending success banner appears once and is gone on the next rerun."""
    os.environ["CRUD_TEST_DB"] = str(tmp_path / "crud.db")
    st.cache_data.clear()
    at = AppTest.from_file(str(APP_DIR / "sql_ui_app.py"), default_timeout=30)
    pending = UiState(update_ok=True, update_message="Saved!")
    at.session_state[state_key_for("acc")] = pending

    at.run()
    assert any("Saved!" in s.value for s in at.success)

    at.run()
    assert not any("Saved!" in s.value for s in at.success)
