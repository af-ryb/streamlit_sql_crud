"""Harness app editing a row with a JSON and a seconds-precise datetime column.

`CRUD_TEST_MODE` picks no-schema (`update`, `create`) or Pydantic
(`update_schema`) mode; the form is shown directly, as inside the open dialog.
"""

import os
from datetime import datetime
from typing import Any

import streamlit as st
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud.create_delete_model import CreateRow
from streamlit_pydantic_crud.lib import set_state
from streamlit_pydantic_crud.update_model import UpdateRow

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "update")
CREATED = datetime(2025, 3, 4, 9, 33, 25, 80000)
META = {"tags": ["a", "b"], "nested": {"n": 1}}


class Base(DeclarativeBase):
    """Declarative base for the harness model."""


class Doc(Base):
    """Table with an int, a nullable JSON and a datetime with seconds."""

    __tablename__ = "doc"

    id: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created: Mapped[datetime | None] = mapped_column(DateTime)

    def __str__(self) -> str:
        return f"Doc {self.id}"


class DocUpdate(BaseModel):
    """Update schema mirroring the table."""

    id: int
    count: int = 0
    meta: dict[str, Any] | None = None
    created: datetime | None = None


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Doc).first():
        s.add(Doc(id=1, count=7, meta=META, created=CREATED))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
set_state("stsql_updated", 0)

if MODE == "create":
    CreateRow(conn, Doc, key="t").show("Doc")
else:
    schema = DocUpdate if MODE == "update_schema" else None
    UpdateRow(conn, Doc, 1, key="t", update_schema=schema).show()
