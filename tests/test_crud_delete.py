"""DeleteRows: row preview and delete error handling."""

from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
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


class FakeState(dict):
    """Session-state stand-in supporting attribute access."""

    def __getattr__(self, name: str) -> Any:
        return self[name]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


@pytest.fixture
def clicked() -> Iterator[MagicMock]:
    """Patch Streamlit so the Delete button is clicked; yield the `log` mock."""
    target = "streamlit_pydantic_crud.create_delete_model"
    with (
        patch(f"{target}.st") as mock_st,
        patch(f"{target}.ss", FakeState(stsql_updated=0)),
        patch(f"{target}.log") as mock_log,
        patch.object(DeleteRows, "get_rows_str", return_value=[]),
    ):
        mock_st.button.return_value = True
        yield mock_log


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


def test_delete_failure_is_logged_as_failure(clicked: MagicMock) -> None:
    """A failing commit is logged with success=False."""
    conn = MagicMock()
    conn.session.__enter__.return_value.commit.side_effect = RuntimeError("boom")

    status, _msg = DeleteRows(conn, Department, [1], key="d").show("Department")

    assert status is False
    assert clicked.call_args.kwargs.get("success") is False


def test_delete_several_existing_rows(
    clicked: MagicMock, engine: Engine, session: Session
) -> None:
    """Every listed row is deleted, the others stay."""
    conn = as_conn(FakeConn(engine))

    status, _msg = DeleteRows(conn, Department, [1, 2], key="d").show("Dept")

    assert status is True
    session.expire_all()
    assert session.get(Department, 1) is None
    assert session.get(Department, 2) is None
    assert session.get(Department, 3) is not None


def test_delete_skips_rows_already_gone(
    clicked: MagicMock, engine: Engine, session: Session
) -> None:
    """A row deleted meanwhile is skipped, the others are still deleted."""
    conn = as_conn(FakeConn(engine))

    status, msg = DeleteRows(conn, Department, [1, 999], key="d").show("Dept")

    assert status is True
    assert msg is not None
    assert "999" in msg
    session.expire_all()
    assert session.get(Department, 1) is None
    assert session.get(Department, 2) is not None


def test_delete_with_no_rows_left_fails_gracefully(
    clicked: MagicMock, engine: Engine, session: Session
) -> None:
    """When none of the rows exist any more nothing is deleted."""
    conn = as_conn(FakeConn(engine))

    status, msg = DeleteRows(conn, Department, [999], key="d").show("Dept")

    assert status is False
    assert msg is not None
    assert "999" in msg
