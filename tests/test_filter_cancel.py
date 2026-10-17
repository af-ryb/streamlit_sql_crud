"""Filter cancel buttons and native clears must drop the filter (L3).

The cancel button used to pop only the URL param, leaving the widget state
applied; a native clear left the stale param in the URL.
"""

from collections.abc import Callable
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.table import params

NAME = "_create_no_dt_filter_Name"
START = "_create_date_filter_start_Born"
END = "_create_date_filter_end_Born"
DATE_BTN = f"st_sql_{START}_{END}_cancel_btn"


def ids(at: AppTest) -> str:
    """Return the IDS line printed by the harness app."""
    return next(m.value for m in at.markdown if m.value.startswith("IDS="))


def test_selectbox_cancel_clears_filter(run_app: Callable[[str], AppTest]) -> None:
    at = run_app("filter_app.py")
    at.selectbox(key=NAME).set_value("P2").run()
    assert ids(at) == "IDS=2"
    assert at.query_params.get("name") == "P2"

    at.button(key=f"{NAME}_btn").click().run()
    assert not at.exception
    assert at.selectbox(key=NAME).value is None
    assert "name" not in at.query_params
    assert ids(at) == "IDS=1,2,3,4"


def test_date_cancel_clears_filter(run_app: Callable[[str], AppTest]) -> None:
    at = run_app("filter_app.py")
    at.date_input(key=START).set_value(date(2020, 1, 3)).run()
    assert ids(at) == "IDS=3,4"
    assert at.query_params.get("born_start") == "2020-01-03"

    at.button(key=DATE_BTN).click().run()
    assert not at.exception
    assert at.date_input(key=START).value is None
    assert "born_start" not in at.query_params
    assert ids(at) == "IDS=1,2,3,4"


def test_selectbox_native_clear_drops_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AppTest cannot send a None selectbox state, so call the on_change."""
    query = {"name": "P2"}
    monkeypatch.setattr(params.st, "query_params", query)
    monkeypatch.setattr(params, "ss", {NAME: None})
    params.set_no_dt_param("name", NAME)
    assert "name" not in query


def test_selectbox_cancel_pushes_none_to_frontend(
    run_app: Callable[[str], AppTest],
) -> None:
    """Popping the state left the browser widget showing the old option."""
    at = run_app("filter_app.py")
    at.selectbox(key=NAME).set_value("P2").run()
    at.button(key=f"{NAME}_btn").click().run()
    proto = at.selectbox(key=NAME).proto
    assert proto.set_value
    assert not proto.HasField("raw_value")


def test_date_cancel_pushes_none_to_frontend(
    run_app: Callable[[str], AppTest],
) -> None:
    at = run_app("filter_app.py")
    at.date_input(key=START).set_value(date(2020, 1, 3)).run()
    at.button(key=DATE_BTN).click().run()
    proto = at.date_input(key=START).proto
    assert proto.set_value
    assert list(proto.value) == []


def test_selected_filter_stays_clearable(run_app: Callable[[str], AppTest]) -> None:
    """A computed index made Streamlit hide the native clear button."""
    at = run_app("filter_app.py")
    at.selectbox(key=NAME).set_value("P2").run()
    assert not at.selectbox(key=NAME).proto.HasField("default")
    assert at.selectbox(key=NAME).value == "P2"


def test_date_filter_labels_are_english(run_app: Callable[[str], AppTest]) -> None:
    at = run_app("filter_app.py")
    assert at.date_input(key=START).label == "Start"
    assert at.date_input(key=END).label == "End"
