"""Foreign key fallback renders a text input, not a dead DB query (#6).

PydanticInputGenerator has no `conn`, so the old live-query branch was
unreachable. The fallback must simply render a text input.
"""

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from streamlit_pydantic_crud.pydantic_utils import PydanticInputGenerator


@patch("streamlit_pydantic_crud.pydantic_utils.st")
def test_fk_fallback_uses_text_input(mock_st: MagicMock) -> None:
    """A configured FK field without loaded options falls back to text input."""

    class Schema(BaseModel):
        dept_id: int

    gen = PydanticInputGenerator(
        schema=Schema,
        foreign_key_options={
            "dept_id": {"query": None, "display_field": "name", "value_field": "id"}
        },
    )
    mock_st.text_input.return_value = "5"

    result = gen._render_foreign_key_input("Dept", "dept_id", None, "k")

    mock_st.text_input.assert_called_once()
    mock_st.selectbox.assert_not_called()
    assert result == "5"
