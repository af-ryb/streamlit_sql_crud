"""ExistingData option caches must key on every input they depend on (#6).

`get_text` was keyed by `(table_name, updated)` only, so the current row's
value and the instance's `default_values` leaked between rows and instances.
"""

from collections.abc import Iterator

import pytest
import streamlit as st
from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud.forms.options import ExistingData
from tests.conftest import Department, Employee


class _OrphanBase(DeclarativeBase):
    """Separate registry whose FK target table is not mapped to a class."""


_GHOST = Table("ghost", _OrphanBase.metadata, Column("id", Integer, primary_key=True))


class _Orphan(_OrphanBase):
    """Child whose FK points at a table that has no mapped model."""

    __tablename__ = "orphan"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("ghost.id"))


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    """Start each test with empty caches."""
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def test_current_row_value_does_not_leak_between_rows(session: Session) -> None:
    """Each row sees its own value appended, not the previously edited row's."""
    defaults = {"is_active": True}
    dept2 = session.get(Department, 2)
    dept4 = session.get(Department, 4)

    first = ExistingData(session, Department, defaults, row=dept2)
    second = ExistingData(session, Department, defaults, row=dept4)

    assert "Dept 2" in first.text["name"]
    assert "Dept 4" in second.text["name"]
    assert "Dept 2" not in second.text["name"]


def test_default_values_are_part_of_the_cache_key(session: Session) -> None:
    """Instances on one table with different defaults get their own options."""
    filtered = ExistingData(session, Department, {"is_active": True})
    unfiltered = ExistingData(session, Department, {})

    assert sorted(filtered.text["name"]) == ["Dept 1", "Dept 3", "Dept 5"]
    assert sorted(unfiltered.text["name"]) == [f"Dept {i}" for i in range(1, 6)]


def test_foreign_opts_resolved_via_registry(session: Session) -> None:
    """FK options are built from the mapped target model."""
    data = ExistingData(session, Employee, {})

    assert [opt.idx for opt in data.fk["department_id"]] == [1, 2, 3, 4, 5]


def test_unmapped_fk_target_falls_back(session: Session) -> None:
    """An FK to a table without a mapped model does not crash.

    Only the current row's value is offered, so the widget still renders.
    """
    assert ExistingData(session, _Orphan, {}).fk["target_id"] == []

    row = _Orphan(id=1, target_id=7)
    opts = ExistingData(session, _Orphan, {}, row=row).fk["target_id"]
    assert [(opt.idx, opt.name) for opt in opts] == [(7, "7")]


def test_fk_opts_append_referenced_row_not_edited_row(session: Session) -> None:
    """The edited row's current FK target is offered, not the row itself."""
    emp = session.get(Employee, 3)
    assert emp is not None
    emp.department_id = 4

    data = ExistingData(session, Employee, {"is_active": True}, row=emp)
    opts = data.fk["department_id"]

    assert [(opt.idx, opt.name) for opt in opts] == [
        (1, "Dept 1"),
        (3, "Dept 3"),
        (5, "Dept 5"),
        (4, "Dept 4"),
    ]
