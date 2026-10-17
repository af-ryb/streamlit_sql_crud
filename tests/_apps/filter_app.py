"""SqlUi with enum, string and date filters for query-param round trips.

The SqlUi key comes from CRUD_TEST_KEY (empty by default), so the same app
covers prefixed and unprefixed filter query-param names.
"""

import os
from datetime import date
from enum import Enum as PyEnum

import streamlit as st
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi

DB = os.environ["CRUD_TEST_DB"]
KEY = os.environ.get("CRUD_TEST_KEY", "")


class Base(DeclarativeBase):
    """Declarative base for the filter harness model."""


class Kind(PyEnum):
    """Python enum stored by member name."""

    HR = "hr"
    ENG = "engineering"


class Person(Base):
    """Table with enum, string and date filter columns."""

    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    kind: Mapped[Kind] = mapped_column(SQLEnum(Kind, name="kind_type"))
    born: Mapped[date] = mapped_column()

    def __str__(self) -> str:
        return self.name


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Person).first():
        s.add_all(
            Person(
                id=i,
                name=f"P{i}",
                kind=Kind.HR if i % 2 else Kind.ENG,
                born=date(2020, 1, i),
            )
            for i in range(1, 5)
        )
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
ui = SqlUi(
    conn=conn,
    read_instance=select(Person),
    edit_create_model=Person,
    available_filter=["name", "kind", "born"],
    key=KEY,
)
st.write("IDS=" + ",".join(str(v) for v in ui.df["id"].tolist()))
