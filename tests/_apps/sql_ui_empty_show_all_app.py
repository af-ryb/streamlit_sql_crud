"""SqlUi over an empty table with "Show All" preselected.

The pager must still get a valid page count (at least one page).
"""

import os

import streamlit as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.table.pagination import OPTS_ITEMS_PAGE

DB = os.environ["CRUD_TEST_DB"]


class Base(DeclarativeBase):
    """Declarative base for the AppTest model."""


class Note(Base):
    """Table left empty on purpose."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column()


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)

conn = st.connection("sql", url=f"sqlite:///{DB}")
ui = SqlUi(
    conn=conn,
    read_instance=select(Note),
    edit_create_model=Note,
    key="note",
    items_per_page_default=OPTS_ITEMS_PAGE.index(None),
)
st.write(f"QTTY={ui.qtty_rows}")
