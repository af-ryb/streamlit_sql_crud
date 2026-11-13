"""`from_json_schema` returns an instance of the class it is called on.

`_typing_subclass` is never called: `ty check` covers it, so a return type of
`PydanticUi` again would fail the checks.
"""

from typing import Any

from pydantic import BaseModel

from streamlit_pydantic_crud import PydanticCrudUi, PydanticUi

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
}


def _typing_subclass() -> None:
    crud_ui: PydanticCrudUi[BaseModel] = PydanticCrudUi.from_json_schema(SCHEMA)
    crud_ui.set_operation_type("update")


def test_subclass_gets_its_own_class() -> None:
    assert type(PydanticCrudUi.from_json_schema(SCHEMA, key="c")) is PydanticCrudUi


def test_base_class_gets_the_base_class() -> None:
    assert type(PydanticUi.from_json_schema(SCHEMA, key="b")) is PydanticUi
