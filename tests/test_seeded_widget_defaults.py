"""Seeded widgets pass no default, so Streamlit has nothing to warn about.

Streamlit logs "created with a default value but also had its value set via
the Session State API" when a widget gets both in one run. The check needs a
server runtime, so the tests record the same condition from the policy hook.
"""

import os
import sqlite3
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pytest
from streamlit.elements.lib import policies
from streamlit.runtime.state import get_session_state
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.config_types import FkOpt
from streamlit_pydantic_crud.forms.pydantic.widgets import seeded_number_value
from tests._apps.plain_forms_models import Level

APP = "seeded_widgets_app.py"
PLAIN_APP = "plain_forms_app.py"

SEEDED: dict[str, Any] = {
    "sw_id": "7",
    "sw_qty": 5,
    "sw_rate": 2.5,
    "sw_name": "Ada",
    "sw_notes": "line",
    "sw_meta": '{\n  "a": 1\n}',
    "sw_is_active": True,
    "sw_born": date(1990, 5, 1),
    "sw_age": 30,
    "sw_ratio": 1.5,
    "sw_price": 9.99,
    "sw_bonus": 3,
    "sw_level": 4,
    "sw_color": "blue",
    "sw_colors": ["green"],
    "sw_tags": ["x", "y"],
    "sw_plan": "team",
    "sw_chart": "bar",
    "sw_days": ["tue"],
    "sw_score": 40,
}

"""The plain (no-schema) edit form of `plain_forms_app.py`: rows 1 and 2."""
PLAIN_ROW: dict[str, Any] = {
    "pf_update_title": "first",
    "pf_update_note": "n1",
    "pf_update_level": Level.MID,
    "pf_update_size": "m",
    "pf_update_maker_id": FkOpt(2, "Bob"),
    "pf_update_count": 5,
    "pf_update_qty": 3,
    "pf_update_ratio": 2.5,
    "pf_update_price": 9.99,
    "pf_update_done": True,
    "pf_update_due": date(2024, 2, 29),
    "pf_update_created": datetime(2025, 3, 4, 9, 33),
    "pf_update_tags": ["x", "y"],
    "pf_update_levels": [Level.LOW, Level.HIGH],
    "pf_update_sizes": ["m"],
}
PLAIN_OTHER_ROW: dict[str, Any] = {
    "pf_update_title": "second",
    "pf_update_note": None,
    "pf_update_level": None,
    "pf_update_size": None,
    "pf_update_maker_id": None,
    "pf_update_count": 8,
    "pf_update_qty": None,
    "pf_update_ratio": 0.5,
    "pf_update_price": None,
    "pf_update_done": False,
    "pf_update_due": None,
    "pf_update_created": datetime(2001, 6, 7, 18, 45),
    "pf_update_tags": [],
    "pf_update_levels": [],
    "pf_update_sizes": [],
}


@pytest.fixture
def conflicts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Collect the keys of widgets given a default and a state value at once."""
    keys: list[str] = []
    check = policies.check_session_state_rules

    def record(
        default_value: Any, key: str | None, writes_allowed: bool = True
    ) -> None:
        state = get_session_state()
        if key and default_value is not None and state.is_new_state_value(key):
            keys.append(key)
        check(default_value=default_value, key=key, writes_allowed=writes_allowed)

    monkeypatch.setattr(policies, "check_session_state_rules", record)
    return keys


@pytest.fixture
def plain_form(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], AppTest]:
    """Return a callable rendering the plain form harness in a given mode."""

    def _run(mode: str) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_MODE", mode)
        at = run_app(PLAIN_APP)
        assert not at.exception
        return at

    return _run


def shown(at: AppTest, prefix: str = "sw_") -> dict[str, Any]:
    """Return the value of every form widget of the harness by key."""
    return {key: w.value for key, w in widgets(at, prefix).items()}


def widgets(at: AppTest, prefix: str) -> dict[str, Any]:
    """Return every form widget whose key starts with `prefix`, by key."""
    elements = [
        *at.text_input,
        *at.text_area,
        *at.checkbox,
        *at.date_input,
        *at.datetime_input,
        *at.number_input,
        *at.selectbox,
        *at.radio,
        *at.multiselect,
        *at.slider,
    ]
    return {w.key: w for w in elements if w.key and w.key.startswith(prefix)}


def test_seeded_form_has_no_default_conflict(
    run_app: Callable[[str], AppTest], conflicts: list[str]
) -> None:
    at = run_app(APP)
    assert not at.exception
    assert conflicts == []


def test_reseeded_form_has_no_default_conflict(
    run_app: Callable[[str], AppTest], conflicts: list[str]
) -> None:
    at = run_app(APP)
    at.button(key="reload").click().run()
    assert not at.exception
    assert conflicts == []


def test_seeded_values_are_shown(run_app: Callable[[str], AppTest]) -> None:
    at = run_app(APP)
    assert not at.exception
    assert shown(at) == SEEDED


def test_seeded_values_survive_a_rerun(run_app: Callable[[str], AppTest]) -> None:
    at = run_app(APP)
    at.run()
    assert not at.exception
    assert shown(at) == SEEDED


@pytest.mark.parametrize(
    ("value", "nullable", "kwargs", "expected"),
    [
        (5, False, {"step": 1}, "min"),
        (2.5, False, {}, "min"),
        (5, False, {"min_value": 1, "max_value": 9}, "min"),
        (5, True, {"step": 1}, None),
        (None, False, {"step": 1}, None),
        (5, False, {}, 5),
        (-7, False, {"max_value": -1}, -7),
    ],
)
def test_number_default_is_dropped_only_when_streamlit_agrees(
    value: Any, nullable: bool, kwargs: dict[str, Any], expected: Any
) -> None:
    """ "min" must give the same number type and stay within the bounds."""
    assert seeded_number_value(value, nullable, kwargs) == expected


def test_pager_moved_through_state_is_the_known_conflict(
    run_app: Callable[[str], AppTest], conflicts: list[str]
) -> None:
    """`st.pagination` always passes its default: only a page move conflicts."""
    at = run_app("pagination_app.py")
    assert conflicts == []
    at.pagination(key="p_pagination").set_value(2).run()
    at.selectbox(key="p_page_size").set_value("100").run()
    assert at.pagination(key="p_pagination").value == 1
    assert conflicts == ["p_pagination"]


@pytest.mark.parametrize("mode", ["update", "create", "copy"])
def test_plain_form_has_no_default_conflict(
    plain_form: Callable[[str], AppTest], conflicts: list[str], mode: str
) -> None:
    plain_form(mode)
    assert conflicts == []


def test_plain_form_shows_the_stored_row(plain_form: Callable[[str], AppTest]) -> None:
    at = plain_form("update")
    assert shown(at, "pf_update_") == PLAIN_ROW
    at.run()
    assert shown(at, "pf_update_") == PLAIN_ROW


def test_plain_form_pushes_the_stored_row_to_the_browser(
    plain_form: Callable[[str], AppTest],
) -> None:
    """The browser keeps a keyed widget's value unless the server pushes one."""
    form = widgets(plain_form("update"), "pf_update_")
    assert [key for key, w in form.items() if not w.proto.set_value] == []


def test_reopened_plain_form_pushes_the_other_row(
    plain_form: Callable[[str], AppTest], conflicts: list[str]
) -> None:
    at = plain_form("update")
    at.button(key="other").click().run()
    assert not at.exception
    form = widgets(at, "pf_update_")
    assert {key: w.value for key, w in form.items()} == PLAIN_OTHER_ROW
    assert [key for key, w in form.items() if not w.proto.set_value] == []
    assert conflicts == []


def test_untouched_plain_form_saves_the_same_row(
    plain_form: Callable[[str], AppTest],
) -> None:
    """Seeded widgets return what `value=` widgets did: the stored values."""
    at = plain_form("update")
    before = stored_item()
    next(b for b in at.button if b.label == "Save").click().run()
    assert not at.exception
    assert "RESULT=True|Updated successfully first" in [m.value for m in at.markdown]
    assert stored_item() == before


def stored_item() -> tuple[Any, ...]:
    """Read the raw row 1 of the plain form harness from SQLite."""
    with sqlite3.connect(os.environ["CRUD_TEST_DB"]) as con:
        return con.execute("SELECT * FROM item WHERE id = 1").fetchone()
