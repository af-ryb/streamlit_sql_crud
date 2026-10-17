"""Analyse Pydantic schema fields for form generation.

UI-free: reads annotations, defaults and constraints and maps each field to
the kind of Streamlit input that renders it.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, get_origin

from loguru import logger
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from streamlit_pydantic_crud.typing_helpers import model_fields, unwrap_optional


def get_pydantic_field_info(schema: type[BaseModel]) -> dict[str, dict[str, Any]]:
    """Extract field information from Pydantic schema for input generation

    Args:
        schema: Pydantic schema class

    Returns:
        Dict mapping field names to their metadata
    """
    try:
        field_info = {}

        for field_name, field in model_fields(schema).items():
            info = {
                "annotation": field.annotation,
                "default": _resolved_default(field),
                "is_required": field.is_required(),
                "description": field.description,
                "constraints": {},
            }

            """Extract validation constraints."""
            constraints = getattr(field, "constraints", None)
            if constraints:
                for constraint in constraints:
                    constraint_type = type(constraint).__name__
                    info["constraints"][constraint_type] = constraint

            """Unwrap Optional / `X | None`; inner_type is the origin
            (e.g. list for list[str])."""
            inner, is_optional = unwrap_optional(field.annotation)
            info["is_optional"] = is_optional or not field.is_required()
            info["inner_type"] = get_origin(inner) or inner

            field_info[field_name] = info

        return field_info

    except Exception:
        logger.exception("Error extracting Pydantic field info")
        raise


def _resolved_default(field: FieldInfo) -> Any:
    """Return the field default, calling ``default_factory``; None if required."""
    if field.is_required():
        return None
    return field.get_default(call_default_factory=True, validated_data={})


def get_streamlit_input_type(pydantic_field_info: dict[str, Any]) -> str:
    """Determine the appropriate Streamlit input type for Pydantic field

    Args:
        pydantic_field_info: Field information from get_pydantic_field_info

    Returns:
        String indicating the Streamlit input type to use
    """
    inner_type = pydantic_field_info.get("inner_type", str)
    if inner_type is list or get_origin(inner_type) is list:
        return "multiselect"

    """Map Python types to Streamlit input types."""
    if inner_type is str:
        return "text_input"
    if inner_type is int:
        return "number_input_int"
    if inner_type is float:
        return "number_input_float"
    if inner_type is bool:
        return "checkbox"
    if inner_type is datetime:
        return "datetime_input"
    if inner_type is date:
        return "date_input"
    if inner_type is Decimal:
        return "number_input_decimal"
    if inner_type is dict:
        return "text_area_json"
    return "text_input"


def is_optional_field(field_info: dict[str, Any]) -> bool:
    """Return True when extracted field info marks the field optional."""
    return bool(field_info.get("is_optional")) or not field_info.get(
        "is_required", True
    )
