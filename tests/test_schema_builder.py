"""Round-trip of pydantic ``model_json_schema()`` through the schema builder."""

from collections.abc import Callable
from datetime import date, datetime
from enum import Enum
from typing import Any, get_args, get_origin

from pydantic import BaseModel, Field
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.forms.schema_builder import (
    create_pydantic_model_from_json_schema as build,
)
from streamlit_pydantic_crud.helpers.typing import (
    is_enum_annotation,
    is_enum_list_annotation,
)


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Address(BaseModel):
    city: str
    zip_code: str | None = None


class Person(BaseModel):
    born: date
    seen_at: datetime
    last_login: datetime | None = None
    address: Address
    color: Color
    fav: Color | None = None
    palette: list[Color] = []


def _annotation(model: type[BaseModel], name: str) -> Any:
    return model.model_fields[name].annotation


# --- bug 2: datetime format --------------------------------------------------


def test_datetime_format_maps_to_datetime() -> None:
    model = build(Person.model_json_schema())
    assert _annotation(model, "seen_at") is datetime
    assert _annotation(model, "born") is date


def test_optional_datetime_maps_to_datetime() -> None:
    model = build(Person.model_json_schema())
    assert _annotation(model, "last_login") == datetime | None


def test_legacy_datetime_format_still_accepted() -> None:
    schema = {"properties": {"ts": {"type": "string", "format": "datetime"}}}
    assert _annotation(build(schema), "ts") is datetime


# --- bug 3: required fields with widget config -------------------------------


def test_required_field_with_widget_stays_required() -> None:
    schema = {
        "properties": {
            "status": {"type": "string", "widget": "selectbox", "kw": {"x": 1}},
            "note": {"type": "string", "widget": "text_area"},
        },
        "required": ["status"],
    }
    model = build(schema, field_options={"status": ["a", "b"]})
    assert model.model_fields["status"].is_required()
    assert not model.model_fields["note"].is_required()
    assert model.model_fields["note"].default is None
    extra = model.model_fields["status"].json_schema_extra
    assert extra == {"widget": "selectbox", "kw": {"x": 1, "options": ["a", "b"]}}


def test_required_field_with_default_uses_default() -> None:
    schema = {
        "properties": {"n": {"type": "integer", "default": 3, "widget": "slider"}},
        "required": ["n"],
    }
    field = build(schema).model_fields["n"]
    assert not field.is_required()
    assert field.default == 3


def test_explicit_null_default_is_optional() -> None:
    schema = {"properties": {"n": {"type": "integer", "default": None}}}
    field = build(schema).model_fields["n"]
    assert not field.is_required()
    assert field.default is None


# --- bug 3: $ref / $defs -------------------------------------------------------


def test_ref_to_nested_model_resolved() -> None:
    model = build(Person.model_json_schema())
    nested = _annotation(model, "address")
    assert issubclass(nested, BaseModel)
    assert set(nested.model_fields) == {"city", "zip_code"}
    assert nested.model_fields["city"].is_required()
    assert model.model_fields["address"].is_required()


def test_ref_to_enum_builds_enum() -> None:
    model = build(Person.model_json_schema())
    color = _annotation(model, "color")
    assert issubclass(color, Enum)
    assert [m.value for m in color] == ["red", "blue"]
    assert _annotation(model, "fav") == color | None


def test_ref_to_enum_reuses_one_class_per_def() -> None:
    model = build(Person.model_json_schema())
    palette = _annotation(model, "palette")
    assert get_origin(palette) is list
    assert get_args(palette) == (_annotation(model, "color"),)


def test_ref_enum_renders_as_selectbox() -> None:
    model = build(Person.model_json_schema())
    assert is_enum_annotation(_annotation(model, "color"))
    assert is_enum_annotation(_annotation(model, "fav"))
    assert is_enum_list_annotation(_annotation(model, "palette"))


def test_built_model_validates_enum_values() -> None:
    model = build(Person.model_json_schema())
    instance = model.model_validate(
        {
            "born": "2020-01-01",
            "seen_at": "2020-01-01T10:00:00",
            "address": {"city": "Oslo"},
            "color": "blue",
        }
    )
    dumped = instance.model_dump()
    assert dumped["color"].value == "blue"
    assert dumped["address"] == {"city": "Oslo", "zip_code": None}


def test_allof_single_ref_resolved() -> None:
    schema = {
        "$defs": {"Color": {"enum": ["red", "blue"], "type": "string"}},
        "properties": {"c": {"allOf": [{"$ref": "#/$defs/Color"}]}},
        "required": ["c"],
    }
    color = _annotation(build(schema), "c")
    assert issubclass(color, Enum)


# --- type mapping ------------------------------------------------------------


class Scalars(BaseModel):
    s: str
    i: int
    f: float
    b: bool
    tags: list[str]
    nums: list[int] | None = None
    widget_field: str = Field(default="x", json_schema_extra={"widget": "text_area"})


def test_scalar_and_list_mapping() -> None:
    model = build(Scalars.model_json_schema())
    assert _annotation(model, "s") is str
    assert _annotation(model, "i") is int
    assert _annotation(model, "f") is float
    assert _annotation(model, "b") is bool
    assert _annotation(model, "tags") == list[str]
    assert _annotation(model, "nums") == list[int] | None
    assert model.model_fields["widget_field"].json_schema_extra == {
        "widget": "text_area"
    }
    assert model.model_fields["widget_field"].default == "x"


def test_array_with_field_options_is_list_of_str() -> None:
    schema = {"properties": {"t": {"type": "array", "items": {"type": "integer"}}}}
    model = build(schema, field_options={"t": ["1", "2"]})
    assert _annotation(model, "t") == list[str]


def test_ref_enum_renders_selectbox_at_runtime(
    run_app: Callable[[str], AppTest],
) -> None:
    at = run_app("json_schema_enum_app.py")
    assert not at.exception
    assert len(at.selectbox) == 1
    assert at.selectbox[0].options == ["red", "blue"]
