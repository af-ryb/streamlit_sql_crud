"""Smoke tests proving the SQLite-backed harness exercises real library code."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from streamlit_pydantic_crud import read_cte
from tests.conftest import Department


def test_session_fixture_is_seeded(session: Session) -> None:
    """The session fixture provides the seeded sample rows."""
    count = len(session.execute(select(Department)).scalars().all())
    assert count == 5


def test_get_stmt_pag_applies_offset_and_limit(session: Session) -> None:
    """get_stmt_pag paginates an ordered statement deterministically."""
    stmt = select(Department.id).order_by(Department.id)
    paged = read_cte.get_stmt_pag(stmt, limit=2, page=2)
    ids = session.execute(paged).scalars().all()
    assert ids == [3, 4]
