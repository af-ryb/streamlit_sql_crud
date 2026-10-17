"""Saving the edit form must keep untouched JSON and datetime values exactly.

The datetime widget has minute precision, and no-schema mode has no JSON
widget, so neither may overwrite the stored value unless the user changed it.
"""

import json
import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.helpers.values import keep_unchanged_datetime

APP = "json_datetime_app.py"
MODES = ["update", "update_schema"]
PREFIX = "t_update"
STORED_CREATED = "2025-03-04 09:33:25.080000"
STORED_META = {"tags": ["a", "b"], "nested": {"n": 1}}


@pytest.fixture
def open_form(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Return a callable rendering the edit form in `mode`."""

    def _open(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        at = run_app(APP)
        assert not at.exception
        return at

    return _open


def save(at: AppTest) -> AppTest:
    """Click the form's Save button and rerun."""
    next(b for b in at.button if b.label == "Save").click().run()
    assert not at.exception
    return at


def stored_row() -> tuple[int, object, str | None]:
    """Read `count`, decoded `meta` and raw `created` of the row from SQLite."""
    with sqlite3.connect(os.environ["CRUD_TEST_DB"]) as con:
        count, meta, created = con.execute(
            "SELECT count, meta, created FROM doc WHERE id = 1"
        ).fetchone()
    return count, json.loads(meta) if meta is not None else None, created


@pytest.mark.parametrize("mode", MODES)
def test_save_keeps_untouched_json_and_datetime(
    open_form: Callable[[str], AppTest], mode: str
) -> None:
    at = open_form(mode)
    at.number_input(key=f"{PREFIX}_count").set_value(8)
    save(at)
    assert stored_row() == (8, STORED_META, STORED_CREATED)


@pytest.mark.parametrize("mode", MODES)
def test_changed_datetime_is_saved(
    open_form: Callable[[str], AppTest], mode: str
) -> None:
    at = open_form(mode)
    at.datetime_input(key=f"{PREFIX}_created").set_value(datetime(2025, 3, 4, 10, 5))
    save(at)
    assert stored_row()[2] == "2025-03-04 10:05:00.000000"


def test_schema_mode_clears_json_to_null(
    open_form: Callable[[str], AppTest],
) -> None:
    at = open_form("update_schema")
    at.text_area(key=f"{PREFIX}_meta").set_value("")
    save(at)
    assert stored_row()[1] is None


def test_no_schema_create_leaves_json_to_column_default(
    open_form: Callable[[str], AppTest],
) -> None:
    at = open_form("create")
    at.number_input(key="t_create_count").set_value(3)
    save(at)
    with sqlite3.connect(os.environ["CRUD_TEST_DB"]) as con:
        (meta,) = con.execute("SELECT meta FROM doc WHERE count = 3").fetchone()
    assert json.loads(meta) == {}


def test_keep_unchanged_datetime_restores_tz_and_seconds() -> None:
    original = datetime(2025, 3, 4, 9, 33, 25, 80000, tzinfo=UTC)
    assert keep_unchanged_datetime(datetime(2025, 3, 4, 9, 33), original) is original


def test_keep_unchanged_datetime_returns_changed_or_cleared_value() -> None:
    original = datetime(2025, 3, 4, 9, 33, 25)
    changed = datetime(2025, 3, 4, 9, 34)
    assert keep_unchanged_datetime(changed, original) is changed
    assert keep_unchanged_datetime(None, original) is None
