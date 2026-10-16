"""DeleteRows: row preview and delete error handling."""

from typing import cast

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.create_delete_model import DeleteRows
from tests.conftest import Department, Employee


class FakeConn:
    """Minimal stand-in for SQLConnection exposing a `session` context."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @property
    def session(self) -> Session:
        """Return a fresh session, like SQLConnection.session."""
        return Session(self.engine)


def as_conn(obj: object) -> SQLConnection:
    """Type a fake connection as SQLConnection for the constructor."""
    return cast("SQLConnection", obj)


def test_rows_preview_is_per_table(engine: Engine, session: Session) -> None:
    """Same ids on two tables must show each table's own rows."""
    st.cache_data.clear()
    conn = as_conn(FakeConn(engine))

    depts = DeleteRows(conn, Department, [1], key="d").get_rows_str(
        "department", [1], 0
    )
    emps = DeleteRows(conn, Employee, [1], key="e").get_rows_str("employee", [1], 0)

    assert depts == ["Dept 1"]
    assert emps == ["Emp 1"]


def test_rows_preview_reflects_edits(engine: Engine, session: Session) -> None:
    """The preview is refreshed once the update counter moves."""
    st.cache_data.clear()
    conn = as_conn(FakeConn(engine))
    rows = DeleteRows(conn, Department, [1], key="d")
    assert rows.get_rows_str("department", [1], 0) == ["Dept 1"]

    session.get_one(Department, 1).name = "Renamed"
    session.commit()

    assert rows.get_rows_str("department", [1], 1) == ["Renamed"]
