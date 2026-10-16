"""Form-data generation: error propagation and field default resolution."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from streamlit_pydantic_crud import PydanticUi
from streamlit_pydantic_crud.pydantic_utils import PydanticInputGenerator


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
