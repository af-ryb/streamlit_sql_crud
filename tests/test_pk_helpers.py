"""Primary-key helpers must support any single-column PK name (issue #10).

The library no longer hardcodes the name "id". A single-column primary key
with any name is supported; composite keys are explicitly out of scope and
must raise a clear error.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from streamlit_pydantic_crud.utils import pk_attr, pk_column, pk_name


class Base(DeclarativeBase):
    """Declarative base for the PK-helper test models."""


class Product(Base):
    """Single-column primary key that is NOT named 'id'."""

    __tablename__ = "product"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.name


class Membership(Base):
    """Composite primary key - out of scope for the helpers."""

    __tablename__ = "membership"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(primary_key=True)


def test_pk_name_returns_custom_column_name() -> None:
    assert pk_name(Product) == "code"


def test_pk_column_returns_the_pk_column() -> None:
    col = pk_column(Product)
    assert col.name == "code"
    assert col.primary_key is True


def test_pk_attr_builds_filter_clauses() -> None:
    """pk_attr must yield a mapped attribute usable in == and .in_()."""
    eq_clause = pk_attr(Product) == "A1"
    in_clause = pk_attr(Product).in_(["A1", "A2"])
    assert "product.code" in str(eq_clause)
    assert "product.code" in str(in_clause)


def test_composite_pk_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        pk_column(Membership)
    with pytest.raises(NotImplementedError):
        pk_name(Membership)


def test_pk_helpers_drive_a_real_query() -> None:
    """End-to-end: a non-'id' PK round-trips through a real query."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        s.add_all([Product(code="A1", name="Widget"), Product(code="B2", name="Gadget")])
        s.commit()

        stmt = select(Product).where(pk_attr(Product) == "B2")
        found = s.execute(stmt).scalar_one()
        assert found.name == "Gadget"

        pk = pk_name(Product)
        assert getattr(found, pk) == "B2"
