"""Two SqlUi instances on one page must not share UI state (#7).

Filters, notifications and the dialog-opened flag used to live in global
`stsql_*` session-state keys, so one instance disturbed the other.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import Block

from tests.conftest import APP_DIR

APP = "two_sql_ui_app.py"
MakeApp = Callable[..., AppTest]


@pytest.fixture
def make_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MakeApp:
    """Return a factory for the two-instance app, not yet run."""

    def _make(order: str = "ab", **state: object) -> AppTest:
        monkeypatch.setenv("CRUD_TEST_ORDER", order)
        os.environ["CRUD_TEST_DB"] = str(tmp_path / "crud.db")
        st.cache_data.clear()
        at = AppTest.from_file(str(APP_DIR / APP), default_timeout=30)
        for name, value in state.items():
            at.session_state[name] = value
        return at

    return _make


def test_filter_in_one_instance_keeps_other_page(make_app: MakeApp) -> None:
    """A filter set in "a" must not reset the page of "b" on each rerun."""
    at = make_app(PAGE_b=2)
    at.run()
    at.selectbox(key="a_create_no_dt_filter_Grp").set_value("x").run()

    for _ in range(3):
        assert first_id(at, "b") == 51
        assert ids(at, "a") == [1, 3, 5]
        at.run()


def test_notification_shows_only_in_its_instance(make_app: MakeApp) -> None:
    """A failed create in "a" is reported in "a", even when "b" renders first."""
    at = make_app(order="ba", DIALOG_a=True)
    at.run()
    save = next(b for b in at.button if b.label == "Save")
    save.click().run()

    assert not at.exception
    assert banners(instance(at, "a"))
    assert not banners(instance(at, "b"))


def test_open_dialog_of_one_instance_keeps_other_buttons(make_app: MakeApp) -> None:
    """The dialog of "a" being open must not swallow a click in "b"."""
    at = make_app(order="ba", DIALOG_a=True)
    at.run()
    at.session_state["DIALOG_a"] = False
    at.button(key="b_stsql_action_add").click().run()

    assert not at.exception
    assert "Item" in [h.value for h in at.subheader]


def ids(at: AppTest, key: str) -> list[int]:
    """Return the row ids printed by instance `key`."""
    prefix = f"IDS_{key}="
    line = next(m.value for m in at.markdown if m.value.startswith(prefix))
    return [int(v) for v in line.removeprefix(prefix).split(",")]


def first_id(at: AppTest, key: str) -> int:
    """Return the first row id shown by instance `key`."""
    return ids(at, key)[0]


def instance(at: AppTest, key: str) -> Block:
    """Return the expander block wrapping instance `key`."""
    return next(e for e in at.expander if e.label == f"Instance {key}")


def banners(block: Block) -> list[str]:
    """Return the texts of success and error banners inside `block`."""
    return [e.value for e in [*block.success, *block.error]]
