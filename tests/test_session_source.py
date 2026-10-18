"""`conn` is any SessionSource: st.connection("sql") or a duck-typed wrapper.

The `_typing_*` functions are never called: `ty check` covers them, so a
`conn` parameter typed `SQLConnection` again would fail the checks.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session
from streamlit.connections import SQLConnection
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.config_types import SessionSource
from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.delete import DeleteRows
from streamlit_pydantic_crud.dialogs.edit import UpdateRow
from tests.conftest import Department

APP = str(Path(__file__).parent / "_apps" / "session_source_app.py")


class WrapperConn:
    """Shaped like the consumer's wrapper: a `session` property, nothing else."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @property
    def session(self) -> Session:
        """Return a new Session."""
        return Session(self.engine)


class NoSession:
    """An object without a `session` attribute."""

    engine: Engine


def _typing_accepts(conn: SessionSource) -> None:
    SqlUi(conn=conn, read_instance=select(Department), edit_create_model=Department)
    SqlUi(conn=conn, model=Department)
    CreateRow(conn, Department)
    UpdateRow(conn, Department, 1)
    DeleteRows(conn, Department, [1], key="d")


def _typing_wrapper(conn: WrapperConn) -> None:
    _typing_accepts(conn)


def _typing_sql_connection(conn: SQLConnection) -> None:
    _typing_accepts(conn)


def _typing_rejects_no_session(conn: NoSession) -> None:
    SqlUi(conn=conn, model=Department)  # ty: ignore[invalid-argument-type]
    CreateRow(conn, Department)  # ty: ignore[invalid-argument-type]


@pytest.fixture
def db(tmp_path: Path) -> str:
    """Path of the SQLite file the harness app seeds."""
    return str(tmp_path / "session_source.db")


@pytest.fixture
def run(db: str, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], AppTest]:
    """Return a callable rendering the duck-typed `conn` app in a scenario."""
    monkeypatch.setenv("CRUD_TEST_DB", db)
    monkeypatch.setenv("CRUD_TEST_MODE", "")

    def _run(mode: str) -> AppTest:
        os.environ["CRUD_TEST_MODE"] = mode
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30).run()
        assert not at.exception, [e.message for e in at.exception]
        return at

    return _run


def line(at: AppTest, prefix: str) -> str:
    """Return the value printed by the app after `prefix=`."""
    return next(
        m.value.removeprefix(f"{prefix}=")
        for m in at.markdown
        if m.value.startswith(f"{prefix}=")
    )


def submit(at: AppTest) -> AppTest:
    """Click the form submit button and rerun the app."""
    button = next(b for b in at.button if (b.key or "").startswith("FormSubmitter"))
    button.click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def members(db: str) -> dict[int, tuple[str, int]]:
    """Map member id to (name, team_id) read straight from the database."""
    with Session(create_engine(f"sqlite:///{db}")) as s:
        rows = s.execute(text("SELECT id, name, team_id FROM member")).all()
    return {row[0]: (row[1], row[2]) for row in rows}


@pytest.mark.parametrize(("mode", "key"), [("table_plain", "p"), ("table_schema", "s")])
def test_session_source_table_renders_and_filters(
    run: Callable[[str], AppTest], mode: str, key: str
) -> None:
    at = run(mode)
    assert line(at, "QTTY") == "12"
    df = at.dataframe(key=f"{key}_df_sql_ui_0").value
    assert df["name"].iloc[0] == "M1"
    name_filter = at.selectbox(key=f"{key}_create_no_dt_filter_Name")
    assert "M2" in name_filter.options
    name_filter.select("M2").run()
    assert not at.exception
    assert line(at, "QTTY") == "1"


def test_session_source_create_plain(run: Callable[[str], AppTest], db: str) -> None:
    at = run("create_plain")
    at.selectbox(key="cp_create_name").select("M5")
    at.selectbox(key="cp_create_team_id").select("Blue")
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    assert members(db)[13] == ("M5", 2)


def test_session_source_create_schema(run: Callable[[str], AppTest], db: str) -> None:
    at = run("create_schema")
    at.text_input(key="cs_create_name").input("New")
    at.selectbox(key="cs_create_team_id").select(2)
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    assert members(db)[13] == ("New", 2)


def test_session_source_update_plain_with_children(
    run: Callable[[str], AppTest], db: str
) -> None:
    at = run("update_plain")
    children = at.dataframe(key="stsql_many_df_team_team_id_member_0").value
    assert list(children.iloc[:, 0]) == ["M1", "M3", "M5", "M7", "M9", "M11"]
    name = at.selectbox(key="up_update_name")
    assert name.value == "Red"
    name.select("Blue")
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    with Session(create_engine(f"sqlite:///{db}")) as s:
        assert s.execute(text("SELECT name FROM team WHERE id = 1")).scalar() == (
            "Blue"
        )


def test_session_source_update_schema(run: Callable[[str], AppTest], db: str) -> None:
    at = run("update_schema")
    at.text_input(key="us_update_name").input("Renamed")
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    assert members(db)[1] == ("Renamed", 1)


def test_session_source_delete(run: Callable[[str], AppTest], db: str) -> None:
    at = run("delete")
    at.button(key="d_delete_del_btn").click().run()
    assert line(at, "RESULT").startswith("True|")
    assert 3 not in members(db)
