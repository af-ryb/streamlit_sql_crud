"""Consumer-shaped models for the read path regression harness.

They live in an importable module so AppTest reruns of the harness script do
not register the tables twice; the seed data is defined here too.
"""

import json
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    Dialect,
    Engine,
    ForeignKey,
    Numeric,
    String,
    Table,
    func,
    select,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)


class Tag(StrEnum):
    """Enum stored in the ARRAY-like `tags` column."""

    HOT = "hot"
    NEW = "new"
    SALE = "sale"


class TagArray(ARRAY):
    """ARRAY of Tag enums stored as JSON text so it works on SQLite.

    It subclasses ARRAY, so the library treats it like a PostgreSQL enum array.
    """

    cache_ok = True

    def __init__(self) -> None:
        super().__init__(SQLEnum(Tag))

    def bind_processor(self, dialect: Dialect) -> Any:
        """Store the member values as a JSON list."""
        return store_tags

    def result_processor(self, dialect: Dialect, coltype: object) -> Any:
        """Load the JSON list back as Tag members."""
        return load_tags


def store_tags(value: list[Tag] | None) -> str | None:
    """Encode a Tag list as JSON text of the member values."""
    return None if value is None else json.dumps([Tag(t).value for t in value])


def load_tags(value: str | None) -> list[Tag] | None:
    """Decode JSON text into a Tag list."""
    return None if value is None else [Tag(t) for t in json.loads(value)]


@compiles(TagArray, "sqlite")
def compile_tag_array(element: TagArray, compiler: Any, **kw: Any) -> str:
    """SQLite has no ARRAY: the column is TEXT."""
    return "TEXT"


class Base(DeclarativeBase):
    """Declarative base for the read path harness."""


item_category = Table(
    "rp_item_category",
    Base.metadata,
    Column("item_id", ForeignKey("rp_item.id"), primary_key=True),
    Column("category_id", ForeignKey("rp_category.id"), primary_key=True),
)


class Template(Base):
    """Related table whose columns the JOIN read query adds as labels."""

    __tablename__ = "rp_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_name: Mapped[str] = mapped_column()
    platform: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.app_name


class Category(Base):
    """Target of the many-to-many relationship; `enabled` feeds the filter."""

    __tablename__ = "rp_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    enabled: Mapped[bool] = mapped_column(default=True)

    def __str__(self) -> str:
        return self.name


class Item(Base):
    """String UUID PK, FK, Numeric(10, 2), JSON, enum ARRAY and M2M."""

    __tablename__ = "rp_item"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column()
    template_id: Mapped[int] = mapped_column(ForeignKey("rp_template.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    meta: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
    tags: Mapped[list[Tag] | None] = mapped_column(TagArray)

    template: Mapped[Template] = relationship()
    categories: Mapped[list[Category]] = relationship(secondary=item_category)

    @property
    def app_name(self) -> str:
        """App name of the template; read schemas need joined labels as attrs."""
        return self.template.app_name

    @property
    def platform(self) -> str:
        """Platform of the template, as stored (the JOIN query upper-cases it)."""
        return self.template.platform

    @property
    def category_names(self) -> str | None:
        """Names of the linked categories, sorted and comma-joined."""
        if not self.categories:
            return None
        return ", ".join(sorted(c.name for c in self.categories))

    def __str__(self) -> str:
        return self.name


class ItemRead(BaseModel):
    """Read schema mirroring every Item column (same table as plain mode)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    template_id: int
    price: Decimal
    meta: dict[str, Any] | list[Any] | None = None
    tags: list[Tag] | None = None


class ItemJoinRead(BaseModel):
    """Read schema of the JOIN query: labels first, no PK field (as hitapps)."""

    model_config = ConfigDict(from_attributes=True)

    app_name: str | None = None
    platform: str | None = None
    name: str
    price: Decimal


class ItemM2MRead(BaseModel):
    """Read schema with a model @property aggregated over the M2M relation."""

    model_config = ConfigDict(from_attributes=True)

    category_names: str | None = None
    app_name: str | None = None
    platform: str | None = None
    name: str
    price: Decimal


"""Insert order (alpha..delta) differs from the PK order of the UUIDs."""
ID_ALPHA = "c3a1e5b2-0000-4000-8000-000000000001"
ID_BRAVO = "0a7d2c4e-0000-4000-8000-000000000002"
ID_CHARLIE = "7f3b9e1d-0000-4000-8000-000000000003"
ID_DELTA = "f19c6a8b-0000-4000-8000-000000000004"
META_ALPHA = {"k": 1, "mixed": [1, "a", None]}


def seed(engine: Engine) -> None:
    """Create the tables and insert the fixed rows once."""
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        if s.get(Template, 1):
            return
        ios = Template(id=1, app_name="Alpha App", platform="ios")
        android = Template(id=2, app_name="Beta App", platform="android")
        red = Category(id=1, name="red", enabled=True)
        green = Category(id=2, name="green", enabled=True)
        blue = Category(id=3, name="blue", enabled=False)
        s.add_all([ios, android, red, green, blue])
        s.add_all(
            [
                Item(
                    id=ID_ALPHA,
                    name="alpha",
                    template=ios,
                    price=Decimal("12.50"),
                    meta=META_ALPHA,
                    tags=[Tag.HOT, Tag.NEW],
                    categories=[red, blue],
                ),
                Item(
                    id=ID_BRAVO,
                    name="bravo",
                    template=android,
                    price=Decimal("3.00"),
                    meta=None,
                    tags=[],
                    categories=[],
                ),
                Item(
                    id=ID_CHARLIE,
                    name="charlie",
                    template=ios,
                    price=Decimal("7.25"),
                    meta={"k": 3},
                    tags=None,
                    categories=[red, green, blue],
                ),
                Item(
                    id=ID_DELTA,
                    name="delta",
                    template=android,
                    price=Decimal("0.10"),
                    meta=[1, 2],
                    tags=[Tag.SALE],
                    categories=[green],
                ),
            ]
        )
        s.commit()


"""Correlated scalar subquery: how many categories an item links to."""
CATEGORY_COUNT = (
    select(func.count(item_category.c.category_id))
    .where(item_category.c.item_id == Item.id)
    .correlate(Item)
    .scalar_subquery()
)
