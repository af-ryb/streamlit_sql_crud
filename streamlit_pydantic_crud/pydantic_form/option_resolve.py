"""Resolve widget defaults and options for Pydantic forms.

UI-free: maps session values, explicit widget kwargs and field defaults onto
the options a selection widget offers.
"""

from enum import Enum
from typing import Any

from loguru import logger

from streamlit_pydantic_crud.typing_helpers import enum_member
from streamlit_pydantic_crud.values import enum_value, to_list


def resolve_select_index(
    session_value: Any,
    explicit_index: int | None,
    field_default: Any,
    options: list,
) -> int | None:
    """Resolve a selectbox/radio index: session > explicit kw > default > 0."""
    if session_value is not None:
        idx = match_option(session_value, options)
        if idx is not None:
            return idx
    if explicit_index is not None:
        return explicit_index
    if field_default is not None:
        idx = match_option(field_default, options)
        if idx is not None:
            return idx
    return 0 if options else None


def resolve_multiselect_default(
    session_value: Any, explicit_default: Any, field_default: Any
) -> list:
    """Resolve a multiselect default list: session > explicit kw > default > []."""
    if session_value is not None:
        return to_list(session_value)
    if explicit_default is not None:
        return to_list(explicit_default)
    if field_default is not None:
        return to_list(field_default)
    return []


def known_defaults(defaults: list, options: list, label: str) -> list:
    """Return defaults mapped onto options, dropping unknown ones with a warning.

    Matching uses ``match_option`` so enum members and values interchange.
    """
    result = []
    for item in defaults:
        idx = match_option(item, options)
        if idx is None:
            logger.warning(f"Dropping default {item!r} not in options of {label}")
        elif options[idx] not in result:
            result.append(options[idx])
    return result


def match_option(value: Any, options: list) -> int | None:
    """Return the index of value in options, matching enum member or value.

    Uses identity-free equality first, then compares by enum .value so a
    member and its value form match interchangeably. Falsy-but-valid
    values (0, False, "") are handled.
    """
    if value is None:
        return None
    for i, opt in enumerate(options):
        if opt == value:
            return i
    target = enum_value(value)
    for i, opt in enumerate(options):
        if enum_value(opt) == target:
            return i
    return None


def enum_list_defaults(existing_value: Any, enum_type: type[Enum]) -> list:
    """Map stored enum items (members, values, names, PG literal) to values.

    Items matching no member are dropped with a warning so the multiselect
    default always stays within its options.
    """
    result = []
    for item in to_list(existing_value):
        member = enum_member(item, enum_type)
        if member is None:
            logger.warning(f"Dropping unknown {enum_type.__name__} value {item!r}")
        elif member.value not in result:
            result.append(member.value)
    return result


def is_float_number_kwargs(widget_kwargs: dict[str, Any]) -> bool:
    """Return True when number widget kwargs (step, bounds) call for floats."""
    min_val = widget_kwargs.get("min_value")
    max_val = widget_kwargs.get("max_value")
    step = widget_kwargs.get("step")

    return bool(
        isinstance(step, float)
        or isinstance(min_val, float)
        or isinstance(max_val, float)
        or (step and "." in str(step))
    )
