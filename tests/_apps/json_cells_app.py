"""Harness app showing a JSON column whose value holds a mixed-type list.

`CRUD_TEST_MODE=schema` reads through a Pydantic `read_schema`; any other value
reads without schemas. The table must render the JSON as indented text.
"""

import os
from typing import Any

import streamlit as st
from pydantic import BaseModel
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "schema")
META = {"mixed": [1, "two", 3.5, None, True]}
ITEMS = [1, "a", {"k": 2}]


class Base(DeclarativeBase):
    """Declarative base for the harness model."""


class Doc(Base):
    """Table with a JSON object column and a JSON list column."""

    __tablename__ = "doc"

    id: Mapped[int] = mapped_column(primary_key=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    items: Mapped[list[Any] | None] = mapped_column(JSON)

    def __str__(self) -> str:
        return f"Doc {self.id}"


class DocRead(BaseModel):
    """Read schema mirroring the table."""

    id: int
    meta: dict[str, Any] | None = None
    items: list[Any] | None = None


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Doc).first():
        s.add(Doc(id=1, meta=META, items=ITEMS))
        s.add(Doc(id=2, meta=None, items=None))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
read_schema = DocRead if MODE == "schema" else None
SqlUi(conn=conn, model=Doc, read_schema=read_schema, key="doc")
