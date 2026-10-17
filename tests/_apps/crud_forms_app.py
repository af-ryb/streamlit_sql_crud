"""Harness app rendering CreateRow/UpdateRow/InputFields in SQLAlchemy mode.

The DB path comes from CRUD_TEST_DB and the scenario from CRUD_TEST_MODE, so
one app covers enum editing, default values and widget key collisions.
Seeding more than ten distinct notes keeps `note` a free-text input.
"""

import os
from datetime import date
from enum import Enum as PyEnum

import streamlit as st
from sqlalchemy import ARRAY, ForeignKey, Numeric, String, create_engine
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.edit import UpdateRow
from streamlit_pydantic_crud.forms.options import ExistingData
from streamlit_pydantic_crud.forms.sa_fields import InputFields
from streamlit_pydantic_crud.state import UPDATED_KEY, set_state

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "fields")


class Base(DeclarativeBase):
    """Declarative base for the harness model."""


class Status(PyEnum):
    """Python enum stored by member name in the database."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Owner(Base):
    """Parent table referenced by Task through a foreign key."""

    __tablename__ = "owner"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.name


class Task(Base):
    """Table covering enum, string, numeric, date and boolean columns."""

    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    note: Mapped[str | None] = mapped_column()
    status: Mapped[Status] = mapped_column(SQLEnum(Status, name="status_type"))
    priority: Mapped[str] = mapped_column(SQLEnum("low", "high", name="prio_type"))
    done: Mapped[bool] = mapped_column(default=False)
    count: Mapped[int] = mapped_column(default=0)
    ratio: Mapped[float] = mapped_column(default=0.0)
    due: Mapped[date | None] = mapped_column()
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("owner.id"))
    qty: Mapped[int | None] = mapped_column()
    score: Mapped[float | None] = mapped_column()
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))

    def __str__(self) -> str:
        return f"Task {self.id}"


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Task).first():
        s.add(Owner(id=1, name="Ann"))
        s.add_all(
            Task(
                id=i,
                note=f"n{i}",
                status=Status.ACTIVE,
                priority="high",
                done=True,
                count=i,
                ratio=0.5,
                amount=i,
                qty=i,
                score=0.5,
                price=i,
            )
            for i in range(1, 13)
        )
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
set_state(UPDATED_KEY, 0)


def render_fields(prefix: str, with_row: bool) -> None:
    """Render every column through InputFields and print the returned values."""
    with conn.session as ses:
        row = ses.get(Task, 1) if with_row else None
        existing = ExistingData(ses, Task, {}, row=row)
        fields = InputFields(Task, prefix, {}, existing)
        for col in Task.__table__.columns:
            value = getattr(row, col.name) if row else None
            result = fields.get_input_value(col, value)
            st.write(f"VAL_{prefix}_{col.name}={result!r}")
        fields.input_array("tags", ARRAY(String), None)


if MODE == "fields":
    render_fields("f", with_row=False)
elif MODE == "fields_row":
    render_fields("r", with_row=True)
elif MODE == "update":
    status, msg = UpdateRow(conn, Task, 1, key="t").show()
    st.write(f"RESULT={status}|{msg}")
    with Session(eng) as s2:
        st.write(f"DB_STATUS={s2.get_one(Task, 1).status!r}")
elif MODE == "two":
    render_fields("a", with_row=False)
    render_fields("b", with_row=False)
    UpdateRow(conn, Task, 1, key="a").show()
    UpdateRow(conn, Task, 1, key="b").show()
elif MODE == "defaults":
    defaults = {"done": False, "count": 0}
    CreateRow(conn, Task, default_values=defaults, key="d").show("Task")
    UpdateRow(conn, Task, 1, default_values=defaults, key="d").show()
