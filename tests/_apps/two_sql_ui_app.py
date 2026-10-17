"""Two SqlUi instances with different keys on one page.

Instance "a" shows a small filterable table, instance "b" a table large enough
to paginate; tests pick its page through the `b_pagination` widget key. The
render order follows CRUD_TEST_ORDER ("ab" by default). While
session state `DIALOG_a` is true the create dialog of "a" is rendered on
every run, standing in for the dialog fragment Streamlit reruns on its own.
"""

import os

import streamlit as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.dialogs.create import CreateRow

DB = os.environ["CRUD_TEST_DB"]
ORDER = os.environ.get("CRUD_TEST_ORDER", "ab")


class Base(DeclarativeBase):
    """Declarative base for the AppTest models."""


class Fruit(Base):
    """Small table with a filterable `grp` column (instance "a")."""

    __tablename__ = "fruit"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    grp: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.name


class Item(Base):
    """Table with more rows than one page (instance "b")."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.label


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Fruit).first():
        s.add_all(
            Fruit(id=i, name=f"F{i}", grp="x" if i % 2 else "y") for i in range(1, 6)
        )
        s.add_all(Item(id=i, label=f"I{i}") for i in range(1, 121))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")


def render(key: str) -> None:
    """Render instance `key` inside its own expander and print its row ids."""
    with st.expander(f"Instance {key}"):
        if key == "a":
            ui = SqlUi(
                conn=conn,
                read_instance=select(Fruit),
                edit_create_model=Fruit,
                available_filter=["grp"],
                key="a",
            )
        else:
            ui = SqlUi(
                conn=conn,
                read_instance=select(Item),
                edit_create_model=Item,
                available_filter=["label"],
                key="b",
            )
        st.write(f"IDS_{key}=" + ",".join(str(v) for v in ui.df["id"].tolist()))


for instance in ORDER:
    render(instance)

if st.session_state.get("DIALOG_a"):
    CreateRow(conn, Fruit, key="a").show_dialog()
