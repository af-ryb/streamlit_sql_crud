"""No-schema string inputs: a selectbox of existing values that takes new ones.

Free-text (`note`, > string_enum_threshold values) and short-string (`kind`)
columns both offer the stored values, accept a typed new value and return
None, not the string "None", when left empty. AppTest can neither type a new
option nor send an empty selectbox, so those are seeded in session state
before the first run.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_DIR
from tests.test_input_fields_enum import RunMode

SeededRun = Callable[[str, object], AppTest]

COLUMNS = ("note", "kind")


def values(at: AppTest) -> list[str]:
    """Return the VAL_ lines printed by the harness."""
    return [m.value for m in at.markdown if m.value.startswith("VAL_")]


def test_empty_text_input_returns_none(run_mode: RunMode) -> None:
    """An untouched free-text column yields None."""
    at = run_mode("fields")

    assert not at.exception
    assert "VAL_f_note=None" in values(at)
    assert "VAL_f_kind=None" in values(at)


def test_prefilled_text_input_returns_value(run_mode: RunMode) -> None:
    """A free-text column pre-filled from the row keeps its value."""
    at = run_mode("fields_row")

    assert "VAL_r_note='n1'" in values(at)
    assert "VAL_r_kind='bug'" in values(at)


@pytest.mark.parametrize("name", COLUMNS)
def test_string_input_offers_existing_values(run_mode: RunMode, name: str) -> None:
    at = run_mode("fields")
    box = at.selectbox(key=f"f_{name}")

    assert box.label == name.capitalize()
    assert box.proto.accept_new_options
    assert "n3" in box.options or "chore" in box.options


@pytest.fixture
def seeded_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SeededRun:
    """Render the "fields_row" scenario with one widget state seeded."""

    def _run(key: str, value: object) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", "fields_row")
        os.environ["CRUD_TEST_DB"] = str(tmp_path / "crud.db")
        st.cache_data.clear()
        at = AppTest.from_file(str(APP_DIR / "crud_forms_app.py"))
        at.session_state[key] = value
        return at.run()

    return _run


def test_null_is_not_offered_as_an_option(run_mode: RunMode) -> None:
    """A NULL among the stored values must not show up as a "None" option."""
    at = run_mode("fields")

    assert at.selectbox(key="f_kind").options == ["bug", "chore"]


@pytest.mark.parametrize("name", COLUMNS)
def test_string_input_accepts_new_value(seeded_run: SeededRun, name: str) -> None:
    at = seeded_run(f"r_{name}", "brand new")

    assert not at.exception
    assert f"VAL_r_{name}='brand new'" in values(at)


@pytest.mark.parametrize("name", COLUMNS)
def test_string_input_can_be_cleared(seeded_run: SeededRun, name: str) -> None:
    at = seeded_run(f"r_{name}", None)

    assert not at.exception
    assert f"VAL_r_{name}=None" in values(at)


@pytest.mark.parametrize("name", COLUMNS)
def test_string_input_empty_text_is_none(seeded_run: SeededRun, name: str) -> None:
    at = seeded_run(f"r_{name}", "")

    assert f"VAL_r_{name}=None" in values(at)
