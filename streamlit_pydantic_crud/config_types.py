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
