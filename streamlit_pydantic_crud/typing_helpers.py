"""Inspect Python and Pydantic type annotations.

Leaf module: depends only on the standard library and pydantic.
"""

import types
from enum import Enum
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


def is_enum_annotation(annotation: Any) -> bool:
    """Return True for an enum annotation, optionally wrapped in Optional."""
    inner, _ = unwrap_optional(annotation)
    return is_enum_type(inner)


def is_enum_list_annotation(annotation: Any) -> bool:
    """Return True for a list of enums, optionally wrapped in Optional."""
    return is_enum_type(list_item_type(annotation))


def is_list_annotation(annotation: Any) -> bool:
    """Return True for a ``list[...]`` annotation, optionally wrapped in Optional."""
    inner, _ = unwrap_optional(annotation)
    return get_origin(inner) is list


def list_item_type(annotation: Any) -> Any:
    """Return T of ``list[T]`` / ``Optional[list[T]]``, else None."""
    inner, _ = unwrap_optional(annotation)
    args = get_args(inner)
    if get_origin(inner) is list and args:
        return args[0]
    return None


def unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """Split ``X | None`` / ``Optional[X]`` into ``(X, True)``.

    Anything else, including unions of several non-None types, is returned
    unchanged as ``(tp, False)``.
    """
    if is_union(tp):
        args = get_args(tp)
        non_none = [arg for arg in args if arg is not type(None)]
        if len(args) == 2 and len(non_none) == 1:
            return non_none[0], True
    return tp, False


def is_union(tp: Any) -> bool:
    """Return True for both ``typing.Union[...]`` and PEP 604 ``X | Y``."""
    return get_origin(tp) in (Union, types.UnionType)


def is_enum_type(tp: Any) -> bool:
    """Return True when ``tp`` is an ``Enum`` subclass (not an unwrapped Optional)."""
    return isinstance(tp, type) and issubclass(tp, Enum)


def enum_member(value: Any, enum_type: type[Enum]) -> Enum | None:
    """Resolve a member from itself, its value, its name or ``"Cls.NAME"``.

    Returns None for None and for anything matching no member.
    """
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    raw = value.value if isinstance(value, Enum) else value
    for member in enum_type:
        if member.value == raw:
            return member
    if isinstance(raw, str):
        name = raw.rsplit(".", 1)[-1]
        return enum_type.__members__.get(name)
    return None


def model_fields(schema: type[BaseModel] | BaseModel) -> dict[str, FieldInfo]:
    """Return a schema's fields, reading them from the class even for instances."""
    cls = schema if isinstance(schema, type) else type(schema)
    return cls.model_fields
