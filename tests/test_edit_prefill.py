"""Edit-form prefill (Pydantic mode) keeps each column's own value type.

A numpy scalar loaded by a custom type becomes its Python value; it is not
cast to the PK's type (a str here).
"""

import enum
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel
from sqlalchemy import Date, Integer, Numeric, String, TypeDecorator, create_engine
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from streamlit.testing.v1 import AppTest


class Kind(enum.Enum):
    """Enum column values."""

    A = "a"
    B = "b"


class NumpyInt(TypeDecorator):
    """Integer column whose loaded values are numpy scalars."""

    impl = Integer
    cache_ok = True

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Return the stored integer as ``np.int64``."""
        return None if value is None else np.int64(value)


class PrefillBase(DeclarativeBase):
    """Declarative base private to this module."""


class Gadget(PrefillBase):
    """Model with a str PK and one column per prefilled type."""

    __tablename__ = "gadget"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[Kind] = mapped_column(SQLEnum(Kind))
    score: Mapped[int | None] = mapped_column(NumpyInt, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class GadgetUpdate(BaseModel):
    """Update schema for Gadget."""

    code: str
    count: int
    price: Decimal
    day: date
    kind: Kind
    score: int | None = None
    note: str | None = None


def _app(db: str) -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud.dialogs.edit import UpdateRow  # noqa: PLC0415
    from tests.test_edit_prefill import Gadget, GadgetUpdate  # noqa: PLC0415

    conn = st.connection("sql", url=f"sqlite:///{db}")
    update = UpdateRow(conn, Gadget, "g1", key="u", update_schema=GadgetUpdate)
    st.text(repr(update.current_values))


def test_edit_prefill_keeps_column_types(tmp_path: Path) -> None:
    db = tmp_path / "prefill.db"
    eng = create_engine(f"sqlite:///{db}")
    PrefillBase.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Gadget(
                code="g1",
                count=3,
                price=Decimal("9.50"),
                day=date(2025, 1, 2),
                kind=Kind.B,
                score=7,
                note=None,
            )
        )
        s.commit()

    at = AppTest.from_function(_app, kwargs={"db": str(db)}).run()
    assert not at.exception
    expected = {
        "code": "g1",
        "count": 3,
        "price": Decimal("9.50"),
        "day": date(2025, 1, 2),
        "kind": Kind.B,
        "score": 7,
        "note": None,
    }
    assert at.text[0].value == repr(expected)
