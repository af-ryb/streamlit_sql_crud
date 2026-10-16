"""Mirror SqlUi filter values to URL query params and restore them.

Param names are prefixed with the SqlUi key (``{key}_{column}``) when a key
is set, so instances on one page keep separate filters.
"""

from datetime import date
from enum import Enum
from typing import Any

import streamlit as st
from sqlalchemy.sql.elements import KeyedColumnElement
from streamlit import session_state as ss

from streamlit_pydantic_crud.filters import FkOpt, safe_python_type


def param_name(prefix: str, name: str) -> str:
    """Return the query-param name for `name`, prefixed by the SqlUi key."""
    return f"{prefix}_{name}" if prefix else name


def get_dt_param(colname: str, prefix: str = ""):
    inicio_param = st.query_params.get(param_name(prefix, f"{colname}_inicio"), None)
    if inicio_param == "":
        inicio = None
    else:
        inicio = inicio_param

    final_param = st.query_params.get(param_name(prefix, f"{colname}_final"), None)
    if final_param == "":
        final = None
    else:
        final = final_param

    return inicio, final


def get_no_dt_param(
    col: KeyedColumnElement, existing: list, prefix: str = ""
) -> int | None:
    """Return the index in `existing` of the option stored in the URL, if any."""
    colname = col.description
    if not colname or safe_python_type(col) is None:
        return None

    param = st.query_params.get(param_name(prefix, colname), None)
    if not param:
        return None

    return next(
        (i for i, opt in enumerate(existing) if param_value(opt) == param), None
    )


def param_value(value: Any) -> str:
    """Serialise a filter option for the URL: enum name, FK id or str()."""
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, FkOpt):
        return str(value.idx)
    return str(value)


def display_value(value: Any) -> str:
    """Return the label of a filter option: the enum value or str()."""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def set_dt_param(colname: str, key: str, suffix: str, prefix: str = ""):
    query_key = param_name(prefix, f"{colname}_{suffix}")
    value = ss[key]
    if isinstance(value, date):
        st.query_params[query_key] = value.strftime("%Y-%m-%d")
    else:
        """A cleared date input yields None: drop the filter param."""
        st.query_params.pop(query_key, None)


def set_no_dt_param(colname: str, key: str, prefix: str = ""):
    name = param_name(prefix, colname)
    value = ss[key]
    if value is None:
        """A cleared selectbox yields None: drop the filter param."""
        st.query_params.pop(name, None)
    else:
        st.query_params[name] = param_value(value)


def clear_filter(widget_keys: list[str], param_names: list[str]) -> None:
    """Reset filter widgets and drop their URL params (button on_click).

    Runs before the rerun, so the widgets render empty again.
    """
    for widget_key in widget_keys:
        ss.pop(widget_key, None)
    for name in param_names:
        st.query_params.pop(name, None)
