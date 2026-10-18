"""Harness rendering SqlUi in the consumer's read shapes (`CRUD_TEST_MODE`).

Modes: `plain` (no schema), `styled` (plain + df_style_formatter/style_fn),
`configured` (plain + column_config), `schema` (read_schema), `join` (JOIN labels), `m2m` (WHERE + ORDER BY subquery
+ M2M + @property). AppTest cannot select
dataframe rows, so session state `SELECT` (row positions) is reported as the
selection; the CRUD dialogs are replaced by recorders writing `CALLS`.
"""

import os
from typing import Any
from unittest.mock import patch

import streamlit as st
from sqlalchemy import create_engine, func, select
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.config_types import ManyToManyFields
from tests._apps.read_path_models import (
    CATEGORY_COUNT,
    Category,
    Item,
    ItemJoinRead,
    ItemM2MRead,
    ItemRead,
    Template,
    seed,
)

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "plain")

seed(create_engine(f"sqlite:///{DB}"))
conn = st.connection("sql", url=f"sqlite:///{DB}")
real_dataframe = DeltaGenerator.dataframe


def fake_dataframe(self: DeltaGenerator, *args: Any, **kwargs: Any) -> Any:
    """Render the table; report the `SELECT` positions as its selection.

    The type of the data passed in is recorded as `DATA_TYPE`.
    """
    st.session_state["DATA_TYPE"] = type(args[0] if args else kwargs["data"])
    result = real_dataframe(self, *args, **kwargs)
    rows = st.session_state.get("SELECT")
    if rows is None:
        return result
    return {"selection": {"rows": rows, "columns": []}}


class Recorder:
    """Stand-in for a CRUD dialog: records its kwargs instead of opening."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def show_dialog(self) -> None:
        """Store the call as (dialog name, kwargs) in session state `CALLS`."""
        name = type(self).__name__
        st.session_state.setdefault("CALLS", []).append((name, self.kwargs))


class CreateRow(Recorder):
    """Records the create/copy dialog."""


class UpdateRow(Recorder):
    """Records the edit dialog."""


class DeleteRows(Recorder):
    """Records the delete dialog."""


def enabled_only(q: Any) -> Any:
    """Callable M2M filter: offer only enabled categories."""
    return q.filter(Category.enabled.is_(True))


M2M: ManyToManyFields = {
    "categories": {
        "relationship": "categories",
        "display_field": "name",
        "filter": enabled_only,
    }
}
FILTER = ["name", "app_name"]
"""User column configs: replace the price default, label a plain column."""
COLUMN_CONFIG = {
    "price": st.column_config.NumberColumn(format="dollar"),
    "name": st.column_config.TextColumn("Item name"),
}


def bold_rows(row: Any) -> list[str]:
    """Row style function: every cell bold."""
    return ["font-weight: bold"] * len(row)


def render() -> SqlUi:
    """Build the SqlUi of the current mode."""
    if MODE == "plain":
        return SqlUi(
            conn=conn,
            read_instance=select(Item),
            edit_create_model=Item,
            available_filter=["name"],
            key="rp",
        )
    if MODE == "styled":
        return SqlUi(
            conn=conn,
            read_instance=select(Item),
            edit_create_model=Item,
            df_style_formatter={"price": "${:,.2f}", "meta": "{:>4}"},
            style_fn=bold_rows,
            key="rp",
        )
    if MODE == "configured":
        return SqlUi(
            conn=conn,
            read_instance=select(Item),
            edit_create_model=Item,
            column_config=COLUMN_CONFIG,
            key="rp",
        )
    if MODE == "schema":
        return SqlUi(
            conn=conn,
            read_instance=select(Item),
            edit_create_model=Item,
            read_schema=ItemRead,
            available_filter=["name"],
            key="rp",
        )
    if MODE == "join":
        stmt = select(
            Item,
            Template.app_name.label("app_name"),
            func.upper(Template.platform).label("platform"),
        ).join(Template, Item.template_id == Template.id)
        return SqlUi(
            conn=conn,
            read_instance=stmt,
            edit_create_model=Item,
            read_schema=ItemJoinRead,
            available_filter=FILTER,
            key="rp",
        )
    stmt = (
        select(
            Item,
            Template.app_name.label("app_name"),
            func.upper(Template.platform).label("platform"),
        )
        .join(Template, Item.template_id == Template.id)
        .where(Item.name != "bravo")
        .order_by(CATEGORY_COUNT, Item.name)
    )
    return SqlUi(
        conn=conn,
        read_instance=stmt,
        edit_create_model=Item,
        read_schema=ItemM2MRead,
        many_to_many_fields=M2M,
        available_filter=FILTER,
        key="rp",
    )


with (
    patch.object(DeltaGenerator, "dataframe", fake_dataframe),
    patch("streamlit_pydantic_crud.sql_ui.CreateRow", CreateRow),
    patch("streamlit_pydantic_crud.sql_ui.UpdateRow", UpdateRow),
    patch("streamlit_pydantic_crud.sql_ui.DeleteRows", DeleteRows),
):
    ui = render()

"""Read before anything touches `ui.df`: was the DataFrame built to render?"""
st.session_state["DF_BUILT"] = "df" in vars(ui)
st.session_state["ROWS"] = ui.rows
st.session_state["QTTY"] = ui.qtty_rows
