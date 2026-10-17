"""The shared CRUD dialog wrapper used by create, edit and delete."""

from collections.abc import Callable

import streamlit as st
from streamlit import session_state as ss

from streamlit_pydantic_crud.state import UPDATED_KEY, get_ui_state, set_state


def show_crud_dialog(
    title: str, key: str, show: Callable[[], tuple[bool | None, str | None]]
) -> None:
    """Open a dialog running `show` and store its result in the `key` UI state.

    Reruns the page once `show` wrote to the database (stsql_updated grew).
    Dismissing it reruns too, so Streamlit drops the unsaved widget values.
    """

    @st.dialog(title, width="large", on_dismiss="rerun")
    def wrap_show() -> None:
        set_state(UPDATED_KEY, 0)
        updated_before = ss[UPDATED_KEY]
        status, msg = show()

        ui_state = get_ui_state(key)
        ui_state.update_ok = status
        ui_state.update_message = msg
        ui_state.opened = True

        if ss[UPDATED_KEY] > updated_before:
            st.rerun()

    wrap_show()
