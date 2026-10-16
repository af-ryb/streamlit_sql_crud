"""`render_with_columns` shares `render`'s form-data logic (JSON parsing etc.)."""

from pydantic import BaseModel
from streamlit.testing.v1 import AppTest


class Config(BaseModel):
    """Schema with a dict field, rendered as a JSON text area."""

    name: str = "x"
    data: dict


def _app() -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud import PydanticUi  # noqa: PLC0415
    from tests.test_render_columns import Config  # noqa: PLC0415

    result = PydanticUi(Config, key="f").render_with_columns(2)
    st.write(f"RESULT={result!r}")


def test_render_with_columns_parses_json_like_render() -> None:
    at = AppTest.from_function(_app).run()
    at.text_area(key="f_data").input('{"a": 1}').run()
    assert not at.exception
    assert at.markdown[-1].value == "RESULT=Config(name='x', data={'a': 1})"
    assert len(at.columns) == 2
