"""Pydantic field default resolves to the widget's initial selection (#5).

Precedence: session value > explicit native kw param > Pydantic default >
fallback (index 0 for selectbox/radio, [] for multiselect). Enum members and
their .value form match interchangeably.
"""

from enum import Enum
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field

from streamlit_pydantic_crud.forms.pydantic.generator import PydanticInputGenerator
from streamlit_pydantic_crud.forms.pydantic.option_resolve import (
    match_option,
    resolve_multiselect_default,
    resolve_select_index,
)
from streamlit_pydantic_crud.forms.pydantic.widgets import (
    render_multiselect,
    render_selectbox,
)


class StrColor(str, Enum):  # noqa: UP042 - exercises the str-mixin Enum case
    RED = "red"
    BLUE = "blue"


class PlainColor(Enum):
    RED = "red"
    BLUE = "blue"


# --- match_option ---------------------------------------------------------


def test_match_option_by_value() -> None:
    assert match_option("blue", ["red", "blue"]) == 1


def test_match_option_str_enum_member() -> None:
    assert match_option(StrColor.BLUE, [StrColor.RED, StrColor.BLUE]) == 1


def test_match_option_plain_enum_value_against_members() -> None:
    assert match_option("blue", [PlainColor.RED, PlainColor.BLUE]) == 1


def test_match_option_plain_enum_member_against_values() -> None:
    assert match_option(PlainColor.BLUE, ["red", "blue"]) == 1


def test_match_option_falsy_zero() -> None:
    assert match_option(0, [2, 1, 0]) == 2


def test_match_option_not_found() -> None:
    assert match_option("green", ["red", "blue"]) is None


# --- resolve_select_index: precedence ------------------------------------


def test_select_index_uses_field_default() -> None:
    assert resolve_select_index(None, None, "blue", ["red", "blue"]) == 1


def test_select_index_explicit_kw_overrides_default() -> None:
    assert resolve_select_index(None, 0, "blue", ["red", "blue"]) == 0


def test_select_index_session_overrides_explicit_and_default() -> None:
    assert resolve_select_index("red", 1, "blue", ["red", "blue"]) == 0


def test_select_index_fallback_zero_when_no_match() -> None:
    assert resolve_select_index(None, None, None, ["red", "blue"]) == 0


def test_select_index_none_for_empty_options() -> None:
    assert resolve_select_index(None, None, None, []) is None


# --- resolve_multiselect_default ------------------------------------------


def test_multiselect_default_from_field_default_list() -> None:
    assert resolve_multiselect_default(None, None, ["a", "b"]) == ["a", "b"]


def test_multiselect_default_wraps_scalar() -> None:
    assert resolve_multiselect_default(None, None, "a") == ["a"]


def test_multiselect_explicit_overrides_default() -> None:
    assert resolve_multiselect_default(None, ["x"], ["a"]) == ["x"]


def test_multiselect_session_empty_respected() -> None:
    assert resolve_multiselect_default([], ["x"], ["a"]) == []


# --- integration: widget wiring -------------------------------------------


@patch("streamlit_pydantic_crud.forms.pydantic.widgets.st")
def test_selectbox_uses_field_default(mock_st: MagicMock) -> None:
    render_selectbox("L", {"options": ["red", "blue"]}, None, "k", field_default="blue")
    mock_st.selectbox.assert_called_once_with(
        "L", options=["red", "blue"], index=1, key="k"
    )


@patch("streamlit_pydantic_crud.forms.pydantic.widgets.st")
def test_selectbox_explicit_index_in_kw_wins_over_default(mock_st: MagicMock) -> None:
    render_selectbox(
        "L", {"options": ["red", "blue"], "index": 0}, None, "k", field_default="blue"
    )
    mock_st.selectbox.assert_called_once_with(
        "L", options=["red", "blue"], index=0, key="k"
    )


@patch("streamlit_pydantic_crud.forms.pydantic.widgets.st")
def test_multiselect_uses_field_default(mock_st: MagicMock) -> None:
    render_multiselect(
        "L", {"options": ["a", "b", "c"]}, None, "k", field_default=["b"]
    )
    mock_st.multiselect.assert_called_once_with(
        "L", options=["a", "b", "c"], default=["b"], key="k"
    )


@patch("streamlit_pydantic_crud.forms.pydantic.widgets.st")
def test_field_input_routes_pydantic_default_to_selectbox(mock_st: MagicMock) -> None:
    """End to end: a selectbox field with no session value selects its default."""

    class Schema(BaseModel):
        color: str = Field(
            default="blue",
            json_schema_extra={
                "widget": "selectbox",
                "kw": {"options": ["red", "blue"]},
            },
        )

    gen = PydanticInputGenerator(schema=Schema, key_prefix="t")
    mock_st.selectbox.return_value = "blue"
    gen.render_field("color", gen.field_info["color"], None, "t_color")
    assert mock_st.selectbox.call_args.kwargs["index"] == 1
