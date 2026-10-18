"""Harness app rendering SqlUi and the CRUD dialogs over SQLModel models.

The DB path comes from CRUD_TEST_DB and the scenario from CRUD_TEST_MODE.
Twelve distinct names make `name` a free-text column, not a short-string one.
"""

import os
from datetime import date
from decimal import Decimal

import streamlit as st
from sqlalchemy import select
from sqlmodel import Session, SQLModel, create_engine

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.config_types import ForeignKeyOptions, ManyToManyFields
from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.delete import DeleteRows
from streamlit_pydantic_crud.dialogs.edit import UpdateRow
from tests._apps.sqlmodel_models import (
    Hero,
    HeroCreate,
    HeroRead,
    HeroUpdate,
    Power,
    Rank,
    Team,
)

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "table_plain")
FK: ForeignKeyOptions = {
    "team_id": {"query": select(Team), "display_field": "name", "value_field": "id"}
}
M2M: ManyToManyFields = {"powers": {"relationship": "powers", "display_field": "name"}}

eng = create_engine(f"sqlite:///{DB}")
SQLModel.metadata.create_all(eng)
with Session(eng) as s:
    if not s.get(Team, 1):
        s.add_all([Team(id=1, name="Avengers"), Team(id=2, name="X-Men")])
        s.add_all([Power(id=1, name="fly"), Power(id=2, name="laser")])
        s.add_all(
            Hero(
                id=i,
                name=f"H{i}",
                rank=Rank.HIGH,
                born=date(2000, 1, i),
                salary=Decimal(i * 10),
                team_id=1,
                meta={"k": i},
            )
            for i in range(1, 13)
        )
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")

if MODE == "table_plain":
    ui = SqlUi(conn=conn, read_instance=select(Hero), edit_create_model=Hero, key="p")
elif MODE == "table_schema":
    ui = SqlUi(
        conn=conn,
        read_instance=select(Hero),
        edit_create_model=Hero,
        read_schema=HeroRead,
        create_schema=HeroCreate,
        update_schema=HeroUpdate,
        foreign_key_options=FK,
        many_to_many_fields=M2M,
        key="s",
    )
elif MODE == "create_plain":
    ok, msg = CreateRow(conn, Hero, key="cp").show("Hero")
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "create_schema":
    ok, msg = CreateRow(
        conn,
        Hero,
        key="cs",
        create_schema=HeroCreate,
        foreign_key_options=FK,
        many_to_many_fields=M2M,
    ).show("Hero")
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "update_plain":
    ok, msg = UpdateRow(conn, Hero, 1, key="up").show()
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "update_schema":
    ok, msg = UpdateRow(
        conn,
        Hero,
        1,
        key="us",
        update_schema=HeroUpdate,
        foreign_key_options=FK,
        many_to_many_fields=M2M,
    ).show()
    st.write(f"RESULT={ok}|{msg}")
elif MODE == "delete":
    ok, msg = DeleteRows(conn, Hero, [3], key="d").show("Hero")
    st.write(f"RESULT={ok}|{msg}")

if MODE.startswith("table"):
    st.write(f"QTTY={ui.qtty_rows}")
    st.write("COLS=" + ",".join(ui.rows[0] if ui.rows else []))
