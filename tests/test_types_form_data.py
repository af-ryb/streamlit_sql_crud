"""Form-data generation: error propagation and field default resolution."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from streamlit_pydantic_crud import PydanticUi
from streamlit_pydantic_crud.pydantic_utils import (
    PydanticInputGenerator,
    PydanticSQLAlchemyConverter,
)


class Simple(BaseModel):
    name: str


def test_generate_form_data_propagates_errors() -> None:
    gen = PydanticInputGenerator(Simple)
    with (
        patch.object(gen, "_render_field_input", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        gen.generate_form_data()


@patch("streamlit_pydantic_crud.pydantic_ui.st")
def test_pydantic_ui_render_reports_generation_error(mock_st: MagicMock) -> None:
    """The caller logs, shows st.error and returns None instead of crashing."""
    mock_st.session_state = {}
    ui = PydanticUi(schema=Simple, key="f")
    with patch.object(
        ui.input_generator, "_render_field_input", side_effect=RuntimeError("boom")
    ):
        assert ui.render() is None
    mock_st.error.assert_called_once()
    assert "boom" in mock_st.error.call_args.args[0]


# --- _render_id_field ---------------------------------------------------------


class WithId(BaseModel):
    id: int | None = None
    name: str


@patch("streamlit_pydantic_crud.pydantic_utils.st")
def test_id_field_shown_in_update_mode_without_value(mock_st: MagicMock) -> None:
    """Update forms always show the read-only id, even before a value is known."""
    gen = PydanticInputGenerator(WithId, key_prefix="f_update", operation_type="update")
    gen._render_id_field("Id", None, key="f_update_id")
    mock_st.text_input.assert_called_once()
    kwargs = mock_st.text_input.call_args.kwargs
    assert kwargs["disabled"] is True
    assert kwargs["value"] == ""


@patch("streamlit_pydantic_crud.pydantic_utils.st")
def test_id_field_hidden_in_create_mode(mock_st: MagicMock) -> None:
    gen = PydanticInputGenerator(WithId, key_prefix="update", operation_type="create")
    assert gen._render_id_field("Id", None, key="update_id") is None
    mock_st.text_input.assert_not_called()


# --- default resolution ---------------------------------------------------------


class Defaults(BaseModel):
    required: str
    plain: int = 5
    tags: list[str] = Field(default_factory=lambda: ["a", "b"])
    level: str = Field(
        default_factory=lambda: "high",
        json_schema_extra={"widget": "selectbox", "kw": {"options": ["low", "high"]}},
    )


def test_field_info_default_resolution() -> None:
    info = PydanticSQLAlchemyConverter.get_pydantic_field_info(Defaults)
    assert info["required"]["default"] is None
    assert info["plain"]["default"] == 5
    assert info["tags"]["default"] == ["a", "b"]
    assert info["level"]["default"] == "high"


@patch("streamlit_pydantic_crud.pydantic_utils.st")
def test_default_factory_prefills_list_widget(mock_st: MagicMock) -> None:
    gen = PydanticInputGenerator(Defaults, key_prefix="f")
    gen._render_field_input(
        "tags", gen.field_info["tags"], list[str], existing_value=None, key="f_tags"
    )
    assert mock_st.multiselect.call_args.kwargs["default"] == ["a", "b"]


@patch("streamlit_pydantic_crud.pydantic_utils.st")
def test_default_factory_selects_custom_widget_option(mock_st: MagicMock) -> None:
    gen = PydanticInputGenerator(Defaults, key_prefix="f")
    gen._render_field_input(
        "level", gen.field_info["level"], str, existing_value=None, key="f_level"
    )
    assert mock_st.selectbox.call_args.kwargs["index"] == 1
