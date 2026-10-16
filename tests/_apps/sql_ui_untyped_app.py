"""SqlUi over a read select containing columns without a Python type.

`literal_column` and an untyped `func.upper` call produce `NullType`, whose
`python_type` raises NotImplementedError; the page must still render.
"""

import os

import streamlit as st
from sqlalchemy import create_engine, func, literal_column, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi

DB = os.environ["CRUD_TEST_DB"]


class Base(DeclarativeBase):
    """Declarative base for the AppTest model."""


class Item(Base):
    """Plain table read through a select with extra untyped columns."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.name


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Item).first():
        s.add_all([Item(id=i, name=f"I{i}") for i in range(1, 4)])
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
read_stmt = select(
    Item.id,
    Item.name,
    literal_column("'x'").label("tag"),
    func.upper(Item.name).label("calc"),
)
ui = SqlUi(conn=conn, read_instance=read_stmt, edit_create_model=Item, key="item")
st.write(f"QTTY={ui.qtty_rows}")
