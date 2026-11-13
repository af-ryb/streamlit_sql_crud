"""JSON columns in plain (no-schema) forms: a text area parsed on save.

Regression: JSON columns had no widget, so plain create and copy dropped them.
An untouched widget must not rewrite the stored value.
"""

import json
import os
import sqlite3
from collections.abc import Callable
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.forms.sa_fields import (
    NO_INPUT,
    json_source,
    parse_json_input,
)
from tests._apps.plain_forms_models import META

APP = "plain_forms_app.py"
RAW_META = json.dumps(META)
CHANGED = '{"b": 2, "a": [true, null]}'


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


def result(at: AppTest) -> str:
    """Return the `RESULT=` line the harness wrote after the form."""
    return next(m.value for m in at.markdown if m.value.startswith("RESULT="))


def stored(row_id: int = 1) -> tuple[str | None, str | None, int]:
    """Read the raw `meta` and `config` text and `revised` of a row."""
    with sqlite3.connect(os.environ["CRUD_TEST_DB"]) as con:
        return con.execute(
            "SELECT meta, config, revised FROM item WHERE id = ?", (row_id,)
        ).fetchone()


def test_edit_shows_the_stored_json_pretty_printed(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("update")
    assert at.text_area(key="pf_update_meta").value == json.dumps(META, indent=2)
    assert at.text_area(key="pf_update_meta").label == "Meta"


def test_untouched_edit_does_not_update_the_row(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = save(plain_form("update"))
    assert result(at) == "RESULT=True|Updated successfully first"
    assert stored() == (RAW_META, '{"k": 1}', 0)


def test_reformatted_json_is_not_rewritten(
    plain_form: Callable[[str], AppTest],
) -> None:
    """The same value typed with other whitespace keeps the stored one."""
    at = plain_form("update")
    at.text_area(key="pf_update_meta").set_value(json.dumps(META))
    save(at)
    assert stored() == (RAW_META, '{"k": 1}', 0)


def test_changed_json_is_saved_in_the_typed_key_order(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("update")
    at.text_area(key="pf_update_meta").set_value(CHANGED)
    save(at)
    assert stored() == (CHANGED, '{"k": 1}', 1)


def test_invalid_json_shows_an_error_and_does_not_save(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("update")
    at.text_area(key="pf_update_meta").set_value('{"a": 1,}')
    at.number_input(key="pf_update_count").set_value(99)
    save(at)

    assert result(at) == "RESULT=None|None"
    assert len(at.error) == 1
    assert at.error[0].value.startswith("Meta: invalid JSON (")
    assert "line 1 column" in at.error[0].value
    assert stored() == (RAW_META, '{"k": 1}', 0)
    assert at.text_area(key="pf_update_meta").value == '{"a": 1,}'


def test_cleared_nullable_json_is_stored_as_sql_null(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("update")
    at.text_area(key="pf_update_meta").set_value("")
    save(at)
    assert stored() == (None, '{"k": 1}', 1)


def test_cleared_required_json_shows_an_error_and_does_not_save(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("update")
    at.text_area(key="pf_update_config").set_value("")
    save(at)
    assert [e.value for e in at.error] == ["Config: a JSON value is required"]
    assert stored() == (RAW_META, '{"k": 1}', 0)


def test_untouched_null_json_stays_null_without_an_update(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("update")
    at.button(key="other").click().run()
    assert at.text_area(key="pf_update_meta").value == ""
    save(at)
    assert stored(2) == (None, "{}", 0)


def test_create_stores_the_typed_json(plain_form: Callable[[str], AppTest]) -> None:
    at = plain_form("create")
    at.selectbox(key="pf_create_title").set_value("first")
    at.text_area(key="pf_create_meta").set_value(CHANGED)
    at.text_area(key="pf_create_config").set_value('{"x": "y"}')
    save(at)
    assert stored(3) == (CHANGED, '{"x": "y"}', 0)


def test_create_without_json_uses_null_or_the_column_default(
    plain_form: Callable[[str], AppTest],
) -> None:
    at = plain_form("create")
    at.selectbox(key="pf_create_title").set_value("first")
    save(at)
    assert stored(3) == (None, "{}", 0)


def test_copy_carries_the_json_over(plain_form: Callable[[str], AppTest]) -> None:
    at = plain_form("copy")
    assert at.text_area(key="pf_create_meta").value == json.dumps(META, indent=2)
    save(at)
    assert stored(3) == (RAW_META, '{"k": 1}', 0)


@pytest.mark.parametrize(
    ("value", "source"),
    [
        (None, ""),
        ("abc", '"abc"'),
        (True, "true"),
        (1.5, "1.5"),
        ([1, "a"], '[\n  1,\n  "a"\n]'),
    ],
)
def test_json_source_is_parseable_json(value: Any, source: str) -> None:
    """Scalars are shown as JSON too, so an edit of them parses back."""
    assert json_source(value) == source


def test_parse_json_input_returns_the_stored_object_when_unchanged() -> None:
    value = {"b": 1, "a": 2}
    assert parse_json_input(json_source(value), value, True) is value
    assert parse_json_input('{"b":1,"a":2}', value, True) is value


@pytest.mark.parametrize("text", ["", "  \n", None])
def test_parse_json_input_leaves_an_empty_unset_value_out(text: str | None) -> None:
    assert parse_json_input(text, None, True) is NO_INPUT
    assert parse_json_input(text, None, False) is NO_INPUT


@pytest.mark.parametrize(
    ("text", "expected"),
    [("", None), ("null", None), ('"abc"', "abc"), ("[1]", [1]), ("true", True)],
)
def test_parse_json_input_parses_a_changed_value(text: str, expected: Any) -> None:
    assert parse_json_input(text, {"a": 1}, True) == expected


def test_parse_json_input_tells_1_from_true() -> None:
    """Python treats 1 == True; the JSON text differs, so it is a change."""
    parsed = parse_json_input('{"a": true}', {"a": 1}, True)
    assert parsed == {"a": True}
    assert parsed["a"] is True


@pytest.mark.parametrize("text", ["", "null"])
def test_parse_json_input_requires_a_value_when_not_nullable(text: str) -> None:
    with pytest.raises(ValueError, match="a JSON value is required"):
        parse_json_input(text, {"a": 1}, False)
