"""Self-contained Streamlit app rendered by AppTest over a SQLite DB.

The DB path is passed via the CRUD_TEST_DB environment variable so each
test run is isolated. Renders a real SqlUi and exposes a few facts as
markdown for assertions.
"""

import os

import streamlit as st
from sqlalchemy import Numeric, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from streamlit_pydantic_crud import SqlUi

DB = os.environ["CRUD_TEST_DB"]


class Base(DeclarativeBase):
    """Declarative base for the AppTest model."""


class Account(Base):
    """Account table with a Numeric column (exercises the read path)."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    def __str__(self) -> str:
        return self.name


eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
with Session(eng) as s:
    if not s.query(Account).first():
        s.add_all([Account(id=i, name=f"A{i}", amount=i * 10) for i in range(1, 6)])
        s.commit()

conn = st.connection("sql", url=f"sqlite:///{DB}")
# Read statement orders id DESC; correct pagination must override it to id ASC.
read_stmt = select(Account).order_by(Account.id.desc())
ui = SqlUi(conn=conn, read_instance=read_stmt, edit_create_model=Account, key="acc")
st.write(f"QTTY={ui.qtty_rows}")
st.write("COLS=" + ",".join(str(c) for c in ui.df.columns))
st.write("IDS=" + ",".join(str(v) for v in ui.df["id"].tolist()))
