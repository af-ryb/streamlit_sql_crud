"""Shared typing aliases for the CRUD configuration dicts and the FkOpt option."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, NotRequired, Protocol, TypedDict

from sqlalchemy import MetaData

OperationType = Literal["create", "update"]


class MappedModel(Protocol):
    """A mapped model class: a `DeclarativeBase` subclass or a SQLModel table.

    Public parameters take `type[MappedModel]`. `metadata` is the only mapping
    attribute both declare in their typing: SQLModel declares no `__table__`,
    and `__tablename__` is `Any` on DeclarativeBase but a ClassVar on SQLModel.
    It cannot tell a SQLModel table from a plain SQLModel schema; SQLAlchemy
    rejects an unmapped class at runtime.
    """

    metadata: ClassVar[MetaData]


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
