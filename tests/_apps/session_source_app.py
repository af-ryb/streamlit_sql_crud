"""Harness app passing a duck-typed SessionSource as `conn`, not SQLConnection.

`EngineConn` mirrors the consumer's wrapper: only a `session` property that
returns a new Session. The DB path comes from CRUD_TEST_DB and the scenario
from CRUD_TEST_MODE. Twelve distinct names keep `name` a free-text column.
"""

import os

import streamlit as st
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, ForeignKey, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.config_types import ForeignKeyOptions
from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.delete import DeleteRows
from streamlit_pydantic_crud.dialogs.edit import UpdateRow

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "table_plain")


class Base(DeclarativeBase):
    """Declarative base for the harness models."""


class Team(Base):
    """Parent table: the FK target and the one-to-many side."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    members: Mapped[list["Member"]] = relationship(back_populates="team")

    def __str__(self) -> str:
        return self.name


class Member(Base):
    """Child table with a foreign key to Team."""

    __tablename__ = "member"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    team: Mapped[Team] = relationship(back_populates="members")

    def __str__(self) -> str:
        return self.name


class MemberRead(BaseModel):
    """Read schema of Member."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team_id: int


class MemberCreate(BaseModel):
    """Create schema of Member."""

    name: str
    team_id: int


class MemberUpdate(MemberCreate):
    """Update schema of Member: the create fields plus the PK."""

    id: int


class EngineConn:
    """Duck-typed connection: no Streamlit base class, only `session`."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @property
    def session(self) -> Session:
        """Return a new Session; the library uses it as a context manager."""
        return Session(self.engine)


FK: ForeignKeyOptions = {
    "team_id": {"query": select(Team), "display_field": "name", "value_field": "id"}
}

eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.get(Team, 1):
        s.add_all([Team(id=1, name="Red"), Team(id=2, name="Blue")])
        s.add_all(
            Member(id=i, name=f"M{i}", team_id=1 if i % 2 else 2) for i in range(1, 13)
        )
        s.commit()

conn = EngineConn(eng)

if MODE == "table_plain":
    ui = SqlUi(conn=conn, model=Member, key="p")
    st.write(f"QTTY={ui.qtty_rows}")
elif MODE == "table_schema":
    ui = SqlUi(
        conn=conn,
        read_instance=select(Member),
        edit_create_model=Member,
        read_schema=MemberRead,
        create_schema=MemberCreate,
        update_schema=MemberUpdate,
        foreign_key_options=FK,
        key="s",
    )
    st.write(f"QTTY={ui.qtty_rows}")
elif MODE == "create_plain":
    ok, msg = CreateRow(conn, Member, key="cp").show("Member")
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "create_schema":
    ok, msg = CreateRow(
        conn, Member, key="cs", create_schema=MemberCreate, foreign_key_options=FK
    ).show("Member")
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "update_plain":
    ok, msg = UpdateRow(conn, Team, 1, update_show_many=True, key="up").show()
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "update_schema":
    ok, msg = UpdateRow(
        conn, Member, 1, key="us", update_schema=MemberUpdate, foreign_key_options=FK
    ).show()
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "delete":
    ok, msg = DeleteRows(conn, Member, [3], key="d").show("Member")
    st.write(f"RESULT={ok}|{msg}")
