"""Harness app copying a row with a JSON column through the real create dialog.

`CRUD_TEST_MODE=schema` uses a Pydantic `create_schema`; any other value the
plain (no-schema) form. AppTest cannot select dataframe rows, so session state
`SELECT` (row positions) is reported as the selection.
"""

import os
from typing import Any
from unittest.mock import patch

import streamlit as st
from pydantic import BaseModel
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud import SqlUi

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "schema")
META = {"k": 1, "mixed": [1, "a", None]}


class Base(DeclarativeBase):
    """Declarative base for the harness model."""


class Note(Base):
    """Table with a text column and a JSON object column."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    def __str__(self) -> str:
        return self.title


class NoteCreate(BaseModel):
    """Create schema with the JSON column."""

    title: str
    meta: dict[str, Any] | None = None


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Note).first():
        s.add(Note(id=1, title="first", meta=META))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
real_dataframe = DeltaGenerator.dataframe


def fake_dataframe(self: DeltaGenerator, *args: Any, **kwargs: Any) -> Any:
    """Render the table; report the `SELECT` positions as its selection."""
    result = real_dataframe(self, *args, **kwargs)
    rows = st.session_state.get("SELECT")
    if rows is None:
        return result
    return {"selection": {"rows": rows, "columns": []}}


with patch.object(DeltaGenerator, "dataframe", fake_dataframe):
    SqlUi(
        conn=conn,
        model=Note,
        create_schema=NoteCreate if MODE == "schema" else None,
        key="note",
    )
