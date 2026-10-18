"""SqlUi over 150 rows for the st.pagination / page-size selector tests.

Rows 1-75 have `grp` "x", the rest "y". When session state `KEEP_ROWS` is
set, rows with a larger id are deleted before rendering, standing in for a
delete made through the UI. The rendered row ids and the row count are
printed as markdown.
"""

import os

import streamlit as st
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.state import record_write

DB = os.environ["CRUD_TEST_DB"]
ROWS = 150


class Base(DeclarativeBase):
    """Declarative base for the pagination harness model."""


class Row(Base):
    """Table with enough rows for three 50-row pages."""

    __tablename__ = "row"

    id: Mapped[int] = mapped_column(primary_key=True)
    grp: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return f"R{self.id}"


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Row).first():
        s.add_all(Row(id=i, grp="x" if i <= ROWS // 2 else "y") for i in range(1, 151))
        s.commit()
    keep = st.session_state.get("KEEP_ROWS")
    if keep is not None and s.query(Row).count() > keep:
        s.execute(delete(Row).where(Row.id > keep))
        s.commit()
        record_write()

conn = st.connection("sql", url=f"sqlite:///{DB}")
ui = SqlUi(
    conn=conn,
    read_instance=select(Row),
    edit_create_model=Row,
    available_filter=["grp"],
    key="p",
)
ids = [r["id"] for r in ui.rows]
st.write(f"QTTY={ui.qtty_rows}")
st.write(f"RANGE={ids[0] if ids else 0}-{ids[-1] if ids else 0}")
