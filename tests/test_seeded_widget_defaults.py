"""Seeded widgets pass no default, so Streamlit has nothing to warn about.

Streamlit logs "created with a default value but also had its value set via
the Session State API" when a widget gets both in one run. The check needs a
server runtime, so the tests record the same condition from the policy hook.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from streamlit.elements.lib import policies
from streamlit.runtime.state import get_session_state
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.forms.pydantic.widgets import seeded_number_value

APP = "seeded_widgets_app.py"

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


def shown(at: AppTest) -> dict[str, Any]:
    """Return the value of every form widget of the harness by key."""
    elements = [
        *at.text_input,
        *at.text_area,
        *at.checkbox,
        *at.date_input,
        *at.number_input,
        *at.selectbox,
        *at.radio,
        *at.multiselect,
        *at.slider,
    ]
    return {w.key: w.value for w in elements if w.key and w.key.startswith("sw_")}


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
