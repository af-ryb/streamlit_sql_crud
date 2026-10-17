"""SqlUi app whose read_instance optionally carries ORM loader options.

CRUD_TEST_OPTIONS=1 adds selectinload(Team.members) to the read statement,
which must not change the rendered rows.
"""

import os

import streamlit as st
from sqlalchemy import ForeignKey, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
)

from streamlit_pydantic_crud import SqlUi

DB = os.environ["CRUD_TEST_DB"]
WITH_OPTIONS = os.environ.get("CRUD_TEST_OPTIONS") == "1"


class Base(DeclarativeBase):
    """Declarative base for the options app models."""


class Team(Base):
    """Parent table with a one-to-many relationship."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    members: Mapped[list["Member"]] = relationship(back_populates="team")

    def __str__(self) -> str:
        return self.name


class Member(Base):
    """Child table referencing Team."""

    __tablename__ = "member"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    team: Mapped[Team] = relationship(back_populates="members")


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Team).first():
        s.add_all([Team(id=i, name=f"T{i}") for i in range(1, 4)])
        s.add_all([Member(id=i, name=f"M{i}", team_id=i % 3 + 1) for i in range(1, 7)])
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
read_stmt = select(Team)
if WITH_OPTIONS:
    read_stmt = read_stmt.options(selectinload(Team.members))
ui = SqlUi(conn=conn, read_instance=read_stmt, edit_create_model=Team, key="team")
st.write("COLS=" + ",".join(str(c) for c in ui.df.columns))
st.write("ROWS=" + ";".join(f"{r.id}:{r.name}" for r in ui.df.itertuples()))
