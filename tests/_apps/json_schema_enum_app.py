"""AppTest harness: a ``$defs`` enum field rendered through PydanticUi."""

from enum import Enum

from pydantic import BaseModel

from streamlit_pydantic_crud import PydanticUi


class Tint(Enum):
    RED = "red"
    BLUE = "blue"


class Form(BaseModel):
    tint: Tint


PydanticUi.from_json_schema(Form.model_json_schema(), key="f").render()
