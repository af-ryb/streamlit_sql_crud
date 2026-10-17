"""One-to-many panel (`show_rel`) of a parent row with many children.

Parent 1 has 120 children, parent 2 has 10. Session state `PARENT` picks the
parent whose panel is rendered (1 by default), standing in for opening the
edit dialog of another row.
"""

import os

import streamlit as st
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)

from streamlit_pydantic_crud.dialogs.one_to_many import show_rel

DB = os.environ["CRUD_TEST_DB"]


class Base(DeclarativeBase):
    """Declarative base for the one-to-many harness."""


class Parent(Base):
    """Parent row owning the children."""

    __tablename__ = "parent"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    children: Mapped[list["Child"]] = relationship(back_populates="parent")

    def __str__(self) -> str:
        return self.name


class Child(Base):
    """Child row pointing at its parent."""

    __tablename__ = "child"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id"))
    parent: Mapped[Parent] = relationship(back_populates="children")

    def __str__(self) -> str:
        return self.name


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Parent).first():
        s.add_all([Parent(id=1, name="P1"), Parent(id=2, name="P2")])
        s.add_all(Child(id=i, name=f"C{i}", parent_id=1) for i in range(1, 121))
        s.add_all(Child(id=i, name=f"C{i}", parent_id=2) for i in range(121, 131))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
show_rel(conn, Parent, st.session_state.get("PARENT", 1), Parent.children.property)
