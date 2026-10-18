"""Shared typing aliases: CRUD configuration dicts, protocols and FkOpt."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, NotRequired, Protocol, TypedDict

from sqlalchemy import MetaData
from sqlalchemy.orm import Session

OperationType = Literal["create", "update"]
"""Main table width/height, as `st.dataframe` takes them (pixels or a keyword)."""
TableWidth = int | Literal["stretch", "content"]
TableHeight = int | Literal["auto", "stretch", "content"]


class MappedModel(Protocol):
    """A mapped model class: a `DeclarativeBase` subclass or a SQLModel table.

    Public parameters take `type[MappedModel]`. `metadata` is the only mapping
    attribute both declare in their typing: SQLModel declares no `__table__`,
    and `__tablename__` is `Any` on DeclarativeBase but a ClassVar on SQLModel.
    It cannot tell a SQLModel table from a plain SQLModel schema; SQLAlchemy
    rejects an unmapped class at runtime.
    """

    metadata: ClassVar[MetaData]


class SessionSource(Protocol):
    """Anything with a read-only `session` property returning a new Session.

    `st.connection("sql")` (SQLConnection) satisfies it, and so does a
    duck-typed wrapper over an engine. The library only uses
    `with conn.session as s:`, so each access must return a fresh Session.
    """

    @property
    def session(self) -> Session:
        """A new SQLAlchemy Session, used as a context manager."""
        ...


class ForeignKeyConfig(TypedDict):
    """One ``foreign_key_options`` entry: the options query and its fields."""

    query: Any
    display_field: str
    value_field: str


class ManyToManyConfig(TypedDict):
    """One ``many_to_many_fields`` entry: relationship and display field."""

    relationship: str
    display_field: str
    filter: NotRequired[Callable[[Any], Any]]


ForeignKeyOptions = Mapping[str, ForeignKeyConfig]
ManyToManyFields = Mapping[str, ManyToManyConfig]


class ForeignKeyData(TypedDict):
    """Preloaded options of one FK field; ``display_map`` maps value → label."""

    options: list[Any]
    display_map: dict[Any, Any] | None


class ManyToManyData(TypedDict):
    """Preloaded related rows of one M2M field and the attributes to show."""

    options: list[Any]
    display_field: str
    pk_name: str


@dataclass
class FkOpt:
    """One foreign-key option: the referenced id and its display text."""

    idx: int
    name: str
