"""SqlUi over one table whose sessions share the server's caches.

While session state `DELETE_IDS` holds ids, the delete dialog of those rows is
rendered on every run, standing in for the dialog Streamlit reruns on its own.
Prints the row count and the `name` filter options.
"""

import os

import streamlit as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.dialogs.delete import DeleteRows

DB = os.environ["CRUD_TEST_DB"]


class Base(DeclarativeBase):
    """Declarative base for the AppTest model."""


class Pet(Base):
    """Small table with a filterable `name` column."""

    __tablename__ = "pet"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.name


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Pet).first():
        s.add_all(Pet(id=i, name=f"P{i}") for i in range(1, 6))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
ui = SqlUi(
    conn=conn,
    read_instance=select(Pet),
    edit_create_model=Pet,
    available_filter=["name"],
    key="pet",
)
names = ui.col_filter.existing_values.get("name", [])
st.write(f"QTTY={ui.qtty_rows}")
st.write("NAMES=" + ",".join(str(v) for v in names))

if ids := st.session_state.get("DELETE_IDS"):
    DeleteRows(conn, Pet, ids, key="pet").show_dialog()
