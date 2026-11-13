"""Shared config types: relation configs, their normalizers, protocols, FkOpt."""

import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, NotRequired, Protocol, TypedDict

from sqlalchemy import MetaData, Select
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


"""The related model is only known at runtime, so the row type stays `Any`."""
OptionsFilter = Callable[[Select[Any]], Select[Any]]


@dataclass(frozen=True)
class ForeignKey:
    """One ``foreign_key_options`` entry: the selectbox options of a field.

    Attributes:
        query: ``select(Related)`` (optionally narrowed) listing the options.
        display_field: Attribute of the related row shown in the selectbox.
        value_field: Attribute of the related row saved in the field.
    """

    query: Select[Any]
    display_field: str
    value_field: str = "id"


@dataclass(frozen=True)
class ManyToMany:
    """One ``many_to_many_fields`` entry: the multiselect of a relationship.

    Attributes:
        display_field: Attribute of the related row shown in the multiselect.
        relationship: SQLAlchemy relationship name; defaults to the mapping key.
        filter: Narrows the ``select(Related)`` that lists the options.
    """

    display_field: str
    relationship: str | None = None
    filter: OptionsFilter | None = None


@dataclass(frozen=True)
class ResolvedManyToMany(ManyToMany):
    """Internal form of `ManyToMany`: `relationship` is always a name."""

    relationship: str


class ForeignKeyConfig(TypedDict):
    """Deprecated dict form of a `ForeignKey` entry (not removed before 0.11.0)."""

    query: Any
    display_field: str
    value_field: NotRequired[str]


class ManyToManyConfig(TypedDict):
    """Deprecated dict form of a `ManyToMany` entry (not removed before 0.11.0)."""

    relationship: NotRequired[str]
    display_field: str
    filter: NotRequired[Callable[[Any], Any]]


"""Public parameter types: entries are config objects or the deprecated dicts."""
ForeignKeyOptions = Mapping[str, ForeignKey | ForeignKeyConfig]
ManyToManyFields = Mapping[str, ManyToMany | ManyToManyConfig]
"""Normalized form every internal module reads (attributes only)."""
ResolvedForeignKeyOptions = Mapping[str, ForeignKey]
ResolvedManyToManyFields = Mapping[str, ResolvedManyToMany]


def resolve_foreign_key_options(
    foreign_key_options: ForeignKeyOptions | None, stacklevel: int = 3
) -> dict[str, ForeignKey]:
    """Return ``foreign_key_options`` as `ForeignKey` objects by field name.

    Dict entries are converted with one DeprecationWarning; the default
    `stacklevel` points it at the caller of the public ``__init__`` calling this.
    """
    options = foreign_key_options or {}
    if any(not isinstance(config, ForeignKey) for config in options.values()):
        warn_dict_entries("foreign_key_options", "ForeignKey", stacklevel + 1)
    return {
        name: config if isinstance(config, ForeignKey) else foreign_key_of(config)
        for name, config in options.items()
    }


def resolve_many_to_many_fields(
    many_to_many_fields: ManyToManyFields | None, stacklevel: int = 3
) -> dict[str, ResolvedManyToMany]:
    """Return ``many_to_many_fields`` with every relationship name resolved.

    A missing ``relationship`` becomes the mapping key. Dict entries are
    converted with one DeprecationWarning (`stacklevel` as for foreign keys).
    """
    fields = many_to_many_fields or {}
    if any(not isinstance(config, ManyToMany) for config in fields.values()):
        warn_dict_entries("many_to_many_fields", "ManyToMany", stacklevel + 1)
    return {name: many_to_many_of(name, config) for name, config in fields.items()}


def warn_dict_entries(parameter: str, replacement: str, stacklevel: int) -> None:
    """Warn that `parameter` got the deprecated dict form of `replacement`."""
    warnings.warn(
        f"Dict entries in '{parameter}' are deprecated since 0.9.2 and will not "
        f"be removed before 0.11.0. Use {replacement}(...) objects: "
        f"from streamlit_pydantic_crud import {replacement}.",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def foreign_key_of(config: ForeignKeyConfig) -> ForeignKey:
    """Convert a deprecated dict entry to a `ForeignKey`."""
    return ForeignKey(
        query=config["query"],
        display_field=config["display_field"],
        value_field=config.get("value_field", "id"),
    )


def many_to_many_of(
    name: str, config: ManyToMany | ManyToManyConfig
) -> ResolvedManyToMany:
    """Return the entry under key `name` with its relationship name resolved."""
    if isinstance(config, ResolvedManyToMany):
        return config
    if isinstance(config, ManyToMany):
        return ResolvedManyToMany(
            display_field=config.display_field,
            relationship=config.relationship or name,
            filter=config.filter,
        )
    return ResolvedManyToMany(
        display_field=config["display_field"],
        relationship=config.get("relationship", name),
        filter=config.get("filter"),
    )


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
