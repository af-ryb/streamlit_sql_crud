"""SqlUi over an empty table with "Show All" preselected.

Spies on `sac.pagination` to record the page sizes it receives, so the test
can check that no zero page size reaches the frontend.
"""

import os
from unittest.mock import patch

import streamlit as st
import streamlit_antd_components as sac
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.sql_ui import OPTS_ITEMS_PAGE

DB = os.environ["CRUD_TEST_DB"]


class Base(DeclarativeBase):
    """Declarative base for the AppTest model."""


class Note(Base):
    """Table left empty on purpose."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column()


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)

conn = st.connection("sql", url=f"sqlite:///{DB}")
with patch.object(sac, "pagination", wraps=sac.pagination) as spy:
    ui = SqlUi(
        conn=conn,
        read_instance=select(Note),
        edit_create_model=Note,
        key="note",
        items_per_page_default=OPTS_ITEMS_PAGE.index(None),
    )
page_sizes = [call.kwargs["page_size"] for call in spy.call_args_list]
st.write(f"QTTY={ui.qtty_rows}")
if page_sizes and min(page_sizes) >= 1:
    st.write("PAGE_SIZE_OK")
