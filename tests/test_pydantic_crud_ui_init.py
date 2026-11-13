"""PydanticCrudUi builds its input generator once per construction."""

from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field
from sqlalchemy import select

from streamlit_pydantic_crud import ForeignKeyField, PydanticCrudUi
from tests.conftest import Department

CALLS: list[int] = []


def counting_factory() -> list[str]:
    """Record each call so the test can count default_factory runs."""
    CALLS.append(1)
    return ["a"]


class Tagged(BaseModel):
    tags: list[str] = Field(default_factory=counting_factory)


@patch("streamlit_pydantic_crud.pydantic_ui.st")
def test_default_factory_runs_once_per_construction(mock_st: MagicMock) -> None:
    mock_st.session_state = {}
    CALLS.clear()
    ui = PydanticCrudUi(schema=Tagged, key="f")
    assert len(CALLS) == 1
    assert ui.input_generator.field_info["tags"]["default"] == ["a"]


@patch("streamlit_pydantic_crud.pydantic_ui.st")
def test_crud_ui_generator_gets_relation_config(mock_st: MagicMock) -> None:
    mock_st.session_state = {}
    fk = {"tags": ForeignKeyField(query=select(Department), display_field="n")}
    ui = PydanticCrudUi(schema=Tagged, key="f", foreign_key_options=fk, pk_name="pk")
    assert ui.input_generator.foreign_key_options == fk
    assert ui.foreign_key_options == fk
    assert ui.many_to_many_fields == {}
    assert ui.input_generator.operation_type == "create"
    assert ui.input_generator.pk_name == "pk"
    assert mock_st.session_state == {"f": {}}
