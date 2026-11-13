"""Harness app showing the plain (no-schema) edit / create forms of `Item`.

`CRUD_TEST_MODE`: `update` edits the row in session state `ROW` (the `other`
button reopens the form on row 2, as the dialog does); `create` / `copy` create.
"""

import os

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.edit import UpdateRow
from tests._apps.plain_forms_models import Base, Item, seed_rows

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "update")

eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Item).first():
        s.add_all(seed_rows())
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")

if MODE == "update":
    reopen = st.button("other", key="other")
    if reopen:
        st.session_state["ROW"] = 2
    update_row = UpdateRow(conn, Item, st.session_state.get("ROW", 1), key="pf")
    if reopen:
        update_row.reset_form_state()
    status, msg = update_row.show()
else:
    initial_data = None
    if MODE == "copy":
        with Session(eng) as s:
            row = s.get_one(Item, 1)
            initial_data = {col.name: getattr(row, col.name) for col in row.__table__.c}
    create_row = CreateRow(conn, Item, key="pf", initial_data=initial_data)
    status, msg = create_row.show("Item")
st.write(f"RESULT={status}|{msg}")
