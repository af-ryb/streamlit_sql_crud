"""PEP 604 ``X | None`` must be detected as Optional, same as ``Optional[X]``."""

from enum import Enum
from typing import Optional
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from streamlit_pydantic_crud.pydantic_utils import (
    PydanticInputGenerator,
    PydanticSQLAlchemyConverter,
)
from streamlit_pydantic_crud.utils import unwrap_optional


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Pep604(BaseModel):
    count: int | None = None
    ratio: float | None = None
    color: Color | None = None
    tags: list[str] | None = None
    colors: list[Color] | None = None


class TypingOptional(BaseModel):
    count: Optional[int] = None  # noqa: UP045 - exercises typing.Optional
    tags: Optional[list[str]] = None  # noqa: UP045 - exercises typing.Optional


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (int | None, (int, True)),
        (Optional[int], (int, True)),  # noqa: UP045 - exercises typing.Optional
        (list[str] | None, (list[str], True)),
        (int, (int, False)),
        (int | str, (int | str, False)),
        (int | str | None, (int | str | None, False)),
    ],
)
def test_unwrap_optional(annotation: object, expected: tuple[object, bool]) -> None:
    assert unwrap_optional(annotation) == expected


def test_field_info_pep604_inner_type() -> None:
    info = PydanticSQLAlchemyConverter.get_pydantic_field_info(Pep604)
    assert info["count"]["inner_type"] is int
    assert info["count"]["is_optional"] is True
    assert info["tags"]["inner_type"] is list


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("count", "number_input_int"),
        ("ratio", "number_input_float"),
        ("tags", "multiselect"),
    ],
)
def test_input_type_pep604(field: str, expected: str) -> None:
    info = PydanticSQLAlchemyConverter.get_pydantic_field_info(Pep604)
    assert PydanticSQLAlchemyConverter.get_streamlit_input_type(info[field]) == expected


def test_input_type_typing_optional_list() -> None:
    info = PydanticSQLAlchemyConverter.get_pydantic_field_info(TypingOptional)
    result = PydanticSQLAlchemyConverter.get_streamlit_input_type(info["tags"])
    assert result == "multiselect"


def test_enum_detection_pep604() -> None:
    gen = PydanticInputGenerator(Pep604)
    assert gen._is_enum_field(Color | None)
    assert gen._is_enum_field(Color)
    assert not gen._is_enum_field(int | None)


def test_list_detection_pep604() -> None:
    assert PydanticInputGenerator._is_list_field(list[str] | None)
    assert not PydanticInputGenerator._is_list_field(int | None)


def test_enum_list_detection_pep604() -> None:
    gen = PydanticInputGenerator(Pep604)
    assert gen._is_enum_list_field(list[Color] | None)
    assert not gen._is_enum_list_field(list[str] | None)
    assert gen._extract_enum_from_list_annotation(list[Color] | None) is Color


def test_render_enum_input_pep604() -> None:
    """The selectbox receives the enum values, not a crash on UnionType."""
    with patch("streamlit_pydantic_crud.pydantic_utils.st.selectbox") as sb:
        sb.return_value = "blue"
        result = PydanticInputGenerator._render_enum_input(
            "Color", Color | None, Color.BLUE, key="k"
        )
    assert result == "blue"
    args, kwargs = sb.call_args
    assert args[1] == ["red", "blue"]
    assert kwargs["index"] == 1
