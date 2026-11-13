"""Models of the plain (no-schema) forms harness `plain_forms_app.py`.

One column per `InputFields` widget kind; arrays are stored as JSON on SQLite,
enum arrays by member name like PostgreSQL's `ARRAY(Enum(...))`.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import ARRAY, JSON, ForeignKey, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

CREATED = datetime(2025, 3, 4, 9, 33, 25, 80000)
OTHER_CREATED = datetime(2001, 6, 7, 18, 45, 10)


class Base(DeclarativeBase):
    """Declarative base for the harness models."""


class Level(PyEnum):
    """Python enum stored by member name in the database."""

    LOW = "low"
    MID = "mid"
    HIGH = "high"


class LevelNames(TypeDecorator):
    """SQLite stand-in of `ARRAY(Enum(Level))`: members in, names stored."""

    impl = JSON
    cache_ok = True

    def process_bind_param(
        self, value: list[Any] | None, dialect: Dialect
    ) -> list[str] | None:
        """Store member names; a name is accepted like PostgreSQL does."""
        if value is None:
            return None
        return [Level[getattr(item, "name", item)].name for item in value]

    def process_result_value(
        self, value: list[str] | None, dialect: Dialect
    ) -> list[Level] | None:
        """Return the members of the stored names."""
        return None if value is None else [Level[name] for name in value]


class Maker(Base):
    """Parent table referenced by Item through a foreign key."""

    __tablename__ = "maker"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.name


class Item(Base):
    """Table with one column per plain-form widget kind."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    note: Mapped[str | None] = mapped_column()
    level: Mapped[Level | None] = mapped_column(SQLEnum(Level, name="level_type"))
    size: Mapped[str | None] = mapped_column(SQLEnum("s", "m", "l", name="size_type"))
    maker_id: Mapped[int | None] = mapped_column(ForeignKey("maker.id"))
    count: Mapped[int] = mapped_column(default=0)
    qty: Mapped[int | None] = mapped_column()
    ratio: Mapped[float] = mapped_column(default=0.0)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    done: Mapped[bool] = mapped_column(default=False)
    due: Mapped[date | None] = mapped_column()
    created: Mapped[datetime | None] = mapped_column()
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String).with_variant(JSON(), "sqlite")
    )
    levels: Mapped[list[Level] | None] = mapped_column(
        ARRAY(SQLEnum(Level, name="level_type")).with_variant(LevelNames(), "sqlite")
    )
    sizes: Mapped[list[str] | None] = mapped_column(
        ARRAY(SQLEnum("s", "m", "l", name="size_type")).with_variant(JSON(), "sqlite")
    )

    def __str__(self) -> str:
        return self.title


def seed_rows() -> list[Any]:
    """Return the makers and two items: a full row and a mostly empty one."""
    return [
        Maker(id=1, name="Ann"),
        Maker(id=2, name="Bob"),
        Item(
            id=1,
            title="first",
            note="n1",
            level=Level.MID,
            size="m",
            maker_id=2,
            count=5,
            qty=3,
            ratio=2.5,
            price=Decimal("9.99"),
            done=True,
            due=date(2024, 2, 29),
            created=CREATED,
            tags=["x", "y"],
            levels=[Level.LOW, Level.HIGH],
            sizes=["m"],
        ),
        Item(
            id=2,
            title="second",
            count=8,
            ratio=0.5,
            done=False,
            created=OTHER_CREATED,
            tags=[],
            levels=[],
            sizes=[],
        ),
    ]
