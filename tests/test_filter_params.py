"""Filter query params: enum round trip and per-instance prefix (L4).

Enum filters used to show and store ``str(member)`` ("Kind.HR"), which was
not restored on reload; params of keyed SqlUi instances were not prefixed.
"""

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.table import params

APP = str(Path(__file__).parent / "_apps" / "filter_app.py")


def kind_key(key: str = "") -> str:
    """Widget key of the Kind filter selectbox for SqlUi `key`."""
    return f"{key}_create_no_dt_filter_Kind"


def ids(at: AppTest) -> str:
    """Return the IDS line printed by the harness app."""
    return next(m.value for m in at.markdown if m.value.startswith("IDS="))


@pytest.fixture
def fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., AppTest]:
    """Return a factory running filter_app with a key and preset query params."""
    monkeypatch.setenv("CRUD_TEST_DB", str(tmp_path / "f.db"))

    def _run(key: str = "", query: dict[str, str] | None = None) -> AppTest:
        os.environ["CRUD_TEST_KEY"] = key
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30)
        for name, value in (query or {}).items():
            at.query_params[name] = value
        return at.run()

    monkeypatch.setenv("CRUD_TEST_KEY", "")
    return _run


def test_enum_options_show_values(fresh: Callable[..., AppTest]) -> None:
    at = fresh()
    assert at.selectbox(key=kind_key()).options == ["engineering", "hr"]


def test_enum_selection_writes_name_param(fresh: Callable[..., AppTest]) -> None:
    at = fresh()
    at.selectbox(key=kind_key()).select_index(1).run()
    assert at.query_params.get("kind") == "HR"
    assert ids(at) == "IDS=1,3"
    assert any("hr" in m.value and "Kind." not in m.value for m in at.markdown)


def test_enum_param_restored_on_reload(fresh: Callable[..., AppTest]) -> None:
    at = fresh(query={"kind": "HR"})
    assert not at.exception
    assert ids(at) == "IDS=1,3"


def test_keyed_instance_prefixes_params(fresh: Callable[..., AppTest]) -> None:
    at = fresh(key="k")
    at.selectbox(key=kind_key("k")).select_index(0).run()
    at.date_input(key="k_create_date_filter_start_Born").set_value(
        date(2020, 1, 3)
    ).run()
    assert at.query_params.get("k_kind") == "ENG"
    assert at.query_params.get("k_born_start") == "2020-01-03"
    assert "kind" not in at.query_params
    assert ids(at) == "IDS=4"


def test_keyed_instance_restores_prefixed_params(
    fresh: Callable[..., AppTest],
) -> None:
    at = fresh(key="k", query={"kind": "HR", "k_name": "P2"})
    assert ids(at) == "IDS=2"


def test_param_name() -> None:
    assert params.param_name("", "kind") == "kind"
    assert params.param_name("k", "kind") == "k_kind"
