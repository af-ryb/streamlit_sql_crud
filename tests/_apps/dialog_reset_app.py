"""Harness app opening CreateRow/UpdateRow dialogs like SqlUi does.

The "open" button mimics the SqlUi action button: the dialog object is built
and `show_dialog()` runs only on that run. Later runs while the dialog stays
open call `show()` directly, mimicking Streamlit's dialog fragment rerun.
"""

import os

import streamlit as st
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from streamlit import session_state as ss

from streamlit_pydantic_crud.create_delete_model import CreateRow
from streamlit_pydantic_crud.state import UPDATED_KEY, set_state
from streamlit_pydantic_crud.update_model import UpdateRow

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "update")


class Base(DeclarativeBase):
    """Declarative base for the harness model."""


class Item(Base):
    """Table with a required int, a boolean and a nullable int."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    done: Mapped[bool] = mapped_column(default=False)
    qty: Mapped[int | None] = mapped_column()

    def __str__(self) -> str:
        return f"Item {self.id}"


class ItemCreate(BaseModel):
    """Create schema; `count` above 1000 fails validation."""

    count: int = Field(default=0, le=1000)
    done: bool = False
    qty: int | None = None


class ItemUpdate(ItemCreate):
    """Update schema."""

    id: int


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Item).first():
        s.add(Item(id=1, count=7, done=False, qty=3))
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
set_state(UPDATED_KEY, 0)

open_btn = st.button("open", key="open")
close_btn = st.button("close", key="close")

dialog: CreateRow | UpdateRow
if MODE == "update":
    dialog = UpdateRow(conn, Item, 1, key="t")
elif MODE == "update_schema":
    dialog = UpdateRow(conn, Item, 1, key="t", update_schema=ItemUpdate)
elif MODE == "create":
    dialog = CreateRow(conn, Item, key="t")
elif MODE == "create_schema":
    dialog = CreateRow(conn, Item, key="t", create_schema=ItemCreate)
else:
    initial = {"id": 1, "count": 7, "done": False, "qty": 3}
    dialog = CreateRow(
        conn, Item, key="t", create_schema=ItemCreate, initial_data=initial
    )

if open_btn:
    ss["dlg_open"] = True
    dialog.show_dialog()
elif close_btn:
    ss["dlg_open"] = False
elif ss.get("dlg_open"):
    if isinstance(dialog, CreateRow):
        dialog.show("Item")
    else:
        dialog.show()

with Session(eng) as s2:
    st.write(f"DB_COUNT={s2.get_one(Item, 1).count}")
