"""Harness app loading a record into a PydanticUi via `update_session_data`.

Mirrors the example "Session State Demo": the form renders first, then the
"load" button calls `update_session_data` and reruns the script.
"""

from datetime import date
from enum import StrEnum

import streamlit as st
from pydantic import BaseModel, Field

from streamlit_pydantic_crud import PydanticUi

RECORD = {
    "name": "John Doe",
    "phone": "555-0101",
    "role": "admin",
    "plan": "pro",
    "is_active": False,
    "birth_date": date(1990, 5, 1),
    "age": 30,
    "count": 5,
}


class Role(StrEnum):
    """User role rendered as an enum selectbox."""

    ADMIN = "admin"
    USER = "user"


class Profile(BaseModel):
    """Schema covering text, selectbox, checkbox, date and number widgets."""

    name: str = Field(..., min_length=1)
    phone: str | None = None
    role: Role = Role.USER
    plan: str = Field(
        "free",
        json_schema_extra={
            "widget": "selectbox",
            "kw": {"options": ["free", "pro", "team"]},
        },
    )
    is_active: bool = True
    birth_date: date | None = None
    age: int | None = 18
    count: int = 0


ui = PydanticUi(schema=Profile, key="sd", session_state_key="sd_data")
ui.render()

if st.button("load", key="load"):
    ui.update_session_data(RECORD)
    st.rerun()
if st.button("clear", key="clear"):
    ui.clear_session_data()
    st.rerun()

st.write(f"DATA={st.session_state.get('sd_data')}")
