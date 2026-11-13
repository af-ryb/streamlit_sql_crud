"""Harness app rendering every seeded Pydantic widget kind with a real value.

Each field has a non-empty default or stored value, so every widget seeds its
session state with a value Streamlit would also accept as its own default.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

import streamlit as st
from pydantic import BaseModel, Field

from streamlit_pydantic_crud import PydanticUi


class Color(StrEnum):
    """Enum rendered as a selectbox and, in a list, as a multiselect."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def widget(kind: str, **kw: Any) -> dict[str, Any]:
    """Return the `json_schema_extra` selecting widget `kind` with `kw`."""
    return {"widget": kind, "kw": kw}


class Everything(BaseModel):
    """Schema with one field per widget renderer; every field gets a value."""

    id: int = 7
    qty: int
    rate: float
    name: str = "Ada"
    notes: str = Field("line", json_schema_extra=widget("text_area"))
    meta: dict[str, Any] = {"a": 1}
    is_active: bool = True
    born: date = date(1990, 5, 1)
    age: int = 30
    ratio: float = 1.5
    price: Decimal = Decimal("9.99")
    bonus: int | None = 3
    level: int = Field(4, json_schema_extra=widget("number_input", max_value=10))
    color: Color = Color.BLUE
    colors: list[Color] = [Color.GREEN]
    tags: list[str] = ["x", "y"]
    plan: str = Field(
        "team", json_schema_extra=widget("selectbox", options=["free", "pro", "team"])
    )
    chart: str = Field(
        "bar", json_schema_extra=widget("radio", options=["area", "line", "bar"])
    )
    days: list[str] = Field(
        ["tue"], json_schema_extra=widget("multiselect", options=["mon", "tue"])
    )
    score: int = Field(
        40, json_schema_extra=widget("slider", min_value=10, max_value=90)
    )


"""A stored id makes the form render the read-only ID field; required
numbers are not nullable, so they take the non-empty number input path."""
STORED: dict[str, Any] = {"id": 7, "qty": 5, "rate": 2.5}
st.session_state.setdefault("sw_data", dict(STORED))
ui = PydanticUi(schema=Everything, key="sw", session_state_key="sw_data")
ui.render()

if st.button("reload", key="reload"):
    ui.update_session_data(Everything(**STORED).model_dump())
    st.rerun()
