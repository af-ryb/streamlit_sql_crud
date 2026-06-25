"""Shared pytest fixtures: in-memory SQLite models for library tests.

These models mirror the common shapes the library handles (a parent table,
a child with a foreign key, a numeric column) so logic can be tested against
a real database without PostgreSQL or Docker.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import Engine, ForeignKey, Numeric, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)
from sqlalchemy.pool import StaticPool
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parent / "_apps"


class Base(DeclarativeBase):
    """Declarative base for the test models."""


class Department(Base):
    """Parent table used for read, filter and foreign key tests."""

    __tablename__ = "department"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    def __str__(self) -> str:
        return self.name


class Employee(Base):
    """Child table with a foreign key and a numeric column."""

    __tablename__ = "employee"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"))
    salary: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    department: Mapped[Department] = relationship()

    def __str__(self) -> str:
        return self.name


@pytest.fixture
def engine() -> Engine:
    """In-memory SQLite engine that persists across connections in one test."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Session seeded with deterministic sample data."""
    with Session(engine) as s:
        s.add_all(
            Department(id=i, name=f"Dept {i}", is_active=i % 2 == 1)
            for i in range(1, 6)
        )
        s.add_all(
            Employee(
                id=i,
                name=f"Emp {i}",
                department_id=(i % 5) + 1,
                salary=i * 100,
            )
            for i in range(1, 11)
        )
        s.commit()
        yield s


@pytest.fixture
def run_app(tmp_path: Path):
    """Return a callable that renders an AppTest app over an isolated DB.

    Clears Streamlit caches first so memoized queries cannot leak between
    runs (the per-connection cache key bug would otherwise cross tests).
    """

    def _run(app_name: str = "sql_ui_app.py") -> AppTest:
        os.environ["CRUD_TEST_DB"] = str(tmp_path / "crud.db")
        st.cache_data.clear()
        at = AppTest.from_file(str(APP_DIR / app_name), default_timeout=30)
        at.run()
        return at

    return _run
