"""Foreign key fallback renders a text input, not a dead DB query (#6).

PydanticInputGenerator has no `conn`, so the old live-query branch was
unreachable. The fallback must simply render a text input.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from streamlit_pydantic_crud import ForeignKey
from streamlit_pydantic_crud.config_types import ResolvedManyToMany
from streamlit_pydantic_crud.forms.pydantic.generator import PydanticInputGenerator
from tests.conftest import Department


@patch("streamlit_pydantic_crud.forms.pydantic.widgets.st")
def test_fk_fallback_uses_text_input(mock_st: MagicMock) -> None:
    """A configured FK field without loaded options falls back to text input."""

    class Schema(BaseModel):
        dept_id: int

    gen = PydanticInputGenerator(
        schema=Schema,
        foreign_key_options={
            "dept_id": ForeignKey(query=select(Department), display_field="name")
        },
    )
    mock_st.text_input.return_value = "5"

    result = gen.render_field("dept_id", gen.field_info["dept_id"], None, "k")

    mock_st.text_input.assert_called_once()
    mock_st.selectbox.assert_not_called()
    assert result == "5"


@patch("streamlit_pydantic_crud.forms.pydantic.widgets.st")
def test_m2m_fallback_logs_one_accurate_warning(
    mock_st: MagicMock, warnings_logged: list[str]
) -> None:
    """An M2M field without loaded options logs one warning naming the cause."""

    class Schema(BaseModel):
        tags: list[int] = []

    gen = PydanticInputGenerator(
        schema=Schema,
        many_to_many_fields={
            "tags": ResolvedManyToMany(display_field="name", relationship="tags")
        },
    )
    mock_st.session_state = {}
    mock_st.text_input.return_value = ""

    gen.render_field("tags", gen.field_info["tags"], None, "k")

    mock_st.text_input.assert_called_once()
    assert len(warnings_logged) == 1
    assert "Many-to-many field tags" in warnings_logged[0]
    assert "foreign_key_options" not in warnings_logged[0]


@pytest.fixture
def warnings_logged() -> Iterator[list[str]]:
    """Collect the loguru warnings emitted during the test."""
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}", level="WARNING")
    yield messages
    logger.remove(sink_id)
