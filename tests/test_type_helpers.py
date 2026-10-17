"""Unit tests for the shared type-detection helpers."""

from enum import Enum
from typing import Optional

import pytest
import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

from streamlit_pydantic_crud.pydantic_utils import is_optional_field
from streamlit_pydantic_crud.typing_helpers import is_enum_type, model_fields
from streamlit_pydantic_crud.utils import is_json_type


class Color(Enum):
    RED = "red"


class Item(BaseModel):
    name: str
    note: str | None = None


class WrappedJson(TypeDecorator):
    impl = sa.JSON
    cache_ok = True


def test_model_fields_on_class_and_instance() -> None:
    assert set(model_fields(Item)) == {"name", "note"}
    assert model_fields(Item(name="a")) is Item.model_fields


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"is_optional": True}, True),
        ({"is_required": False}, True),
        ({"is_optional": False, "is_required": True}, False),
        ({}, False),
    ],
)
def test_is_optional_field(info: dict, expected: bool) -> None:
    assert is_optional_field(info) is expected


@pytest.mark.parametrize(
    ("tp", "expected"),
    [
        (Color, True),
        (str, False),
        (Color | None, False),
        (Optional[Color], False),  # noqa: UP045 - exercises typing.Optional
        (list[Color], False),
        (None, False),
    ],
)
def test_is_enum_type(tp: object, expected: bool) -> None:
    assert is_enum_type(tp) is expected


@pytest.mark.parametrize(
    ("col_type", "expected"),
    [
        (sa.JSON(), True),
        (JSONB(), True),
        (WrappedJson(), True),
        (sa.String(), False),
        (sa.Integer(), False),
    ],
)
def test_is_json_type(col_type: sa.types.TypeEngine, expected: bool) -> None:
    assert is_json_type(col_type) is expected
