"""Enum ARRAY columns in plain (no-schema) forms.

Regression: the multiselect mixed raw members with the `.enums` names, so a
stored item showed as `Level.LOW` next to the option `LOW`.
"""

import json
import os
import sqlite3
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import ARRAY
from sqlalchemy import Enum as SQLEnum
from streamlit.testing.v1 import AppTest

from tests._apps.plain_forms_models import Level

APP = "plain_forms_app.py"
NAMES = ["LOW", "MID", "HIGH"]


@pytest.fixture
def plain_form(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Return a callable rendering the plain form harness in a given mode."""

    def _run(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        at = run_app(APP)
        assert not at.exception
        return at

    return _run


def save(at: AppTest) -> AppTest:
    """Click the form's Save button and rerun."""
    next(b for b in at.button if b.label == "Save").click().run()
    assert not at.exception
    return at


def stored(column: str, where: str = "id = 1") -> Any:
    """Read the decoded raw value of an array `column` from SQLite."""
    with sqlite3.connect(os.environ["CRUD_TEST_DB"]) as con:
        (raw,) = con.execute(f"SELECT {column} FROM item WHERE {where}").fetchone()
    return None if raw is None else json.loads(raw)


@pytest.mark.parametrize(
    ("mode", "prefix"), [("update", "pf_update"), ("copy", "pf_create")]
)
def test_enum_array_shows_names_in_options_and_selection(
    plain_form: Callable[[str], AppTest], mode: str, prefix: str
) -> None:
    levels = plain_form(mode).multiselect(key=f"{prefix}_levels")
    assert levels.options == NAMES
    assert levels.value == [Level.LOW, Level.HIGH]
    assert [levels.format_func(item) for item in levels.value] == ["LOW", "HIGH"]


def test_string_enum_array_shows_its_values(
    plain_form: Callable[[str], AppTest],
) -> None:
    sizes = plain_form("update").multiselect(key="pf_update_sizes")
    assert sizes.options == ["s", "m", "l"]
    assert sizes.value == ["m"]


def test_untouched_enum_arrays_are_saved_unchanged(
    plain_form: Callable[[str], AppTest],
) -> None:
    save(plain_form("update"))
    assert stored("levels") == ["LOW", "HIGH"]
    assert stored("sizes") == ["m"]


def test_changed_enum_arrays_are_saved(plain_form: Callable[[str], AppTest]) -> None:
    at = plain_form("update")
    at.multiselect(key="pf_update_levels").set_value([Level.MID])
    at.multiselect(key="pf_update_sizes").set_value(["s", "l"])
    save(at)
    assert stored("levels") == ["MID"]
    assert stored("sizes") == ["s", "l"]


def test_copy_carries_enum_arrays_over(plain_form: Callable[[str], AppTest]) -> None:
    save(plain_form("copy"))
    assert stored("levels", "id = 3") == ["LOW", "HIGH"]
    assert stored("sizes", "id = 3") == ["m"]


def test_create_saves_selected_enum_members(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("create")
    at.selectbox(key="pf_create_title").set_value("first")
    at.multiselect(key="pf_create_levels").set_value([Level.HIGH])
    save(at)
    assert stored("levels", "id = 3") == ["HIGH"]


def _enum_array_app() -> None:
    from types import SimpleNamespace  # noqa: PLC0415 - AppTest serialises this

    import streamlit as st  # noqa: PLC0415

    from streamlit_pydantic_crud.forms.sa_fields import InputFields  # noqa: PLC0415

    existing = SimpleNamespace(text={})
    fields = InputFields(object, "a", {}, existing)  # ty: ignore[invalid-argument-type]
    result = fields.input_array(
        "levels", st.session_state["COL_TYPE"], st.session_state["STORED"]
    )
    st.write(f"RESULT={result!r}")


@pytest.mark.parametrize(
    "stored_value",
    ["{LOW,HIGH}", ["LOW", "HIGH"], ["Level.LOW", "high"], ["LOW", "GONE", "HIGH"]],
    ids=["pg-literal", "names", "repr-and-value", "unknown-dropped"],
)
def test_enum_array_resolves_stored_items_to_members(stored_value: Any) -> None:
    """Names, values, `Cls.NAME` and a PG literal all select the members."""
    at = AppTest.from_function(_enum_array_app)
    at.session_state["COL_TYPE"] = ARRAY(SQLEnum(Level))
    at.session_state["STORED"] = stored_value
    at.run()

    assert not at.exception
    assert at.multiselect(key="a_levels").value == [Level.LOW, Level.HIGH]
    assert f"RESULT={[Level.LOW, Level.HIGH]!r}" in [m.value for m in at.markdown]
