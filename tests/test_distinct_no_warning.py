"""Distinct-value queries must use select().distinct(), not unary distinct().

SQLAlchemy 2.1 warns about column-level distinct() outside an aggregate;
the installed 2.0 does not, so the statements are inspected instead.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
import streamlit as st
from sqlalchemy import Select, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import UnaryExpression

from streamlit_pydantic_crud.forms.options import ExistingData
from streamlit_pydantic_crud.state import UPDATED_KEY
from streamlit_pydantic_crud.table.filter_ui import get_existing_values
from tests.conftest import Department


@pytest.fixture
def executed(session: Session) -> Iterator[list[Select]]:
    """Record every statement the seeded session executes."""
    st.cache_data.clear()
    st.session_state[UPDATED_KEY] = 1
    stmts: list[Select] = []
    original = session.execute

    def spy(stmt: Any, *args: Any, **kwargs: Any) -> Any:
        stmts.append(stmt)
        return original(stmt, *args, **kwargs)

    with patch.object(session, "execute", spy):
        yield stmts


def assert_select_distinct(stmts: list[Select]) -> None:
    """Every statement is SELECT DISTINCT without a unary distinct column."""
    assert stmts
    for stmt in stmts:
        assert stmt._distinct
        for col in stmt.selected_columns:
            unary = isinstance(col, UnaryExpression)
            assert not (unary and col.operator is operators.distinct_op)


def test_existing_values_select_distinct(
    session: Session, executed: list[Select]
) -> None:
    values = get_existing_values(session, select(Department).cte(), 0, ["name"])
    assert values["name"] == [f"Dept {i}" for i in range(1, 6)]
    assert_select_distinct(executed)


def test_str_opts_select_distinct(session: Session, executed: list[Select]) -> None:
    data = ExistingData(session, Department, {})
    assert sorted(data.text["name"]) == [f"Dept {i}" for i in range(1, 6)]
    assert_select_distinct([s for s in executed if len(s.selected_columns) == 1])
