"""Submitting with empty required fields shows a warning (M2).

The form used to return None silently, so saving looked like a no-op.
"""

from pydantic import BaseModel, Field
from streamlit.testing.v1 import AppTest


class Person(BaseModel):
    name: str
    email: str = Field(description="E-mail address")
    age: int | None = None


def _app() -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud import PydanticUi  # noqa: PLC0415
    from tests.test_required_warning import Person  # noqa: PLC0415

    model, submitted = PydanticUi(Person, key="p").render_with_submit("Save")
    st.write(f"RESULT={model!r}|{submitted}")


def test_no_warning_before_submit() -> None:
    at = AppTest.from_function(_app).run()
    assert not at.exception
    assert len(at.warning) == 0


def test_warning_lists_missing_required_on_submit() -> None:
    at = AppTest.from_function(_app).run()
    at.text_input(key="p_name").input("Ann")
    at.button[0].click().run()
    assert not at.exception
    assert len(at.warning) == 1
    msg = at.warning[0].value
    assert "E-mail address" in msg
    assert "Name" not in msg
    assert "Age" not in msg


def test_no_warning_when_complete() -> None:
    at = AppTest.from_function(_app).run()
    at.text_input(key="p_name").input("Ann")
    at.text_input(key="p_email").input("a@b.c")
    at.button[0].click().run()
    assert len(at.warning) == 0
    assert any("name='Ann'" in m.value for m in at.markdown)
