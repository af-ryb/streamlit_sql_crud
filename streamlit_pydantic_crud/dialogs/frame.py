"""The shared CRUD dialog wrapper used by create, edit and delete."""

from collections.abc import Callable

import streamlit as st

from streamlit_pydantic_crud.state import get_ui_state, session_writes


def show_crud_dialog(
    title: str, key: str, show: Callable[[], tuple[bool | None, str | None]]
) -> None:
    """Open a dialog running `show` and store its result in the `key` UI state.

    Reruns the page once `show` wrote to the database (`session_writes` grew).
    Dismissing it reruns too, so Streamlit drops the unsaved widget values.
    """

    @st.dialog(title, width="large", on_dismiss="rerun")
    def wrap_show() -> None:
        writes_before = session_writes()
        status, msg = show()

        ui_state = get_ui_state(key)
        ui_state.update_ok = status
        ui_state.update_message = msg
        ui_state.opened = True

        if session_writes() > writes_before:
            st.rerun()

    wrap_show()
