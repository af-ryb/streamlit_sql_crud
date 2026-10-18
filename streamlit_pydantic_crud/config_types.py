"""Shared typing aliases for the CRUD configuration dicts."""

from collections.abc import Callable, Mapping
from typing import Any, Literal, NotRequired, TypedDict

OperationType = Literal["create", "update"]


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
