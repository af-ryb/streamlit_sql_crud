"""The success/error banner shows once, not on every rerun (#8)."""

import os
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_DIR


def test_notification_clears_after_one_render(tmp_path: Path) -> None:
    """A pending success banner appears once and is gone on the next rerun."""
    os.environ["CRUD_TEST_DB"] = str(tmp_path / "crud.db")
    st.cache_data.clear()
    at = AppTest.from_file(str(APP_DIR / "sql_ui_app.py"), default_timeout=30)
    at.session_state["stsql_update_ok"] = True
    at.session_state["stsql_update_message"] = "Saved!"

    at.run()
    assert any("Saved!" in s.value for s in at.success)

    at.run()
    assert not any("Saved!" in s.value for s in at.success)
