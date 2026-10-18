"""One-to-many relationship panels shown in the SqlUi edit dialog.

Each panel lists, creates and deletes the child rows of the edited row.
"""

from functools import cached_property
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import Select, select
from sqlalchemy.orm import (
    DeclarativeBase,
    RelationshipDirection,
    RelationshipProperty,
    Session,
)
from streamlit.runtime.scriptrunner import get_script_run_ctx

from streamlit_pydantic_crud.config_types import SessionSource
from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.delete import DeleteRows
from streamlit_pydantic_crud.helpers.display import get_pretty_name
from streamlit_pydantic_crud.helpers.sa_model import (
    model_by_tablename,
    pk_attr,
    pk_column,
    tablename,
)
from streamlit_pydantic_crud.state import (
    clear_state_keys,
    data_version,
    session_writes,
)
from streamlit_pydantic_crud.table import pagination, query


class ReadManyRel:
    """Query the child rows that `rel` links to the row `model_id` of `model`."""

    def __init__(
        self,
        model: type[DeclarativeBase],
        model_id: int | str,
        rel: RelationshipProperty,
    ) -> None:
        self.model = model
        self.model_id = model_id
        self.rel = rel

    @cached_property
    def other_col(self) -> Any:
        pairs = self.rel.local_remote_pairs
        if pairs is None:
            msg = f"Relationship {self.rel} has no local/remote column pairs"
            raise ValueError(msg)
        col = pairs[0][1]
        return col

    @cached_property
    def other_model(self) -> type[DeclarativeBase]:
        """The model mapped to the child table, from `model`'s registry."""
        table_name: str = self.other_col.table.name
        other_model = model_by_tablename(self.model, table_name)
        if other_model is None:
            msg = f"No mapped model for table '{table_name}' of relationship {self.rel}"
            raise ValueError(msg)
        return other_model

    @cached_property
    def suffix_key(self) -> str:
        """Widget-key suffix: parent table, child FK column and child table."""
        return f"{tablename(self.model)}_{self.other_col.name}_{self.rel.target}"

    @property
    def base_stmt(self) -> Select[Any]:
        stmt = select(pk_attr(self.other_model), self.other_model)

        if self.model != self.other_model:
            stmt = stmt.join(self.model, pk_attr(self.model) == self.other_col)

        stmt = stmt.where(self.other_col == self.model_id)
        return stmt

    def get_qtty_rows(self, conn: SessionSource) -> int:
        """Count the child rows; cached per statement and data version."""
        return query.get_qtty_rows(conn, self.base_stmt, data_version())

    def get_stmt_pag(self, items_per_page: int, page: int) -> Select[Any]:
        """Return page `page` of the child rows, ordered by primary key."""
        return query.get_stmt_pag(
            self.base_stmt, items_per_page, page, [pk_column(self.other_model)]
        )

    def get_data(
        self, session: Session, items_per_page: int, page: int
    ) -> list[tuple[int, str]]:
        stmt = self.get_stmt_pag(items_per_page, page)
        rows = session.execute(stmt)

        result: list[tuple[int, str]] = [(row[0], str(row[1])) for row in rows]
        return result


@st.fragment
def show_rel(
    conn: SessionSource,
    model: type[DeclarativeBase],
    model_id: int | str,
    rel: RelationshipProperty,
) -> None:
    """Render the Read/Create/Delete panel of one one-to-many relationship."""
    read_many_rel = ReadManyRel(model, model_id, rel)

    exp_name = f"{rel.target} - {read_many_rel.other_col.name}"
    pretty_name = get_pretty_name(exp_name)

    with st.expander(pretty_name):
        tab_read, tab_create, tab_delete = st.tabs(["Read", "Create", "Delete"])
        data_container = tab_read.container()
        pag_container = tab_read.container()

    with pag_container:
        qtty_rows = read_many_rel.get_qtty_rows(conn)
        items_per_page, page = pagination.show_pagination(
            qtty_rows,
            pagination.REL_OPTS_ITEMS_PAGE,
            key=f"stsql_read_many_pag_{read_many_rel.suffix_key}",
        )

    with conn.session as s:
        data = read_many_rel.get_data(s, items_per_page, page)

    with data_container:
        """A write renews the key, dropping a selection of rows that moved."""
        df = pd.DataFrame(data, columns=["id", pretty_name]).set_index("id", drop=True)
        selection_state = st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            selection_mode="multi-row",
            on_select="rerun",
            key=f"stsql_many_df_{read_many_rel.suffix_key}_{session_writes()}",
        )

        rows_pos = []
        if "selection" in selection_state and "rows" in selection_state["selection"]:
            rows_pos = selection_state["selection"]["rows"]

        with tab_create:
            default_values = {read_many_rel.other_col.name: model_id}
            create_key = f"stsql_create_many_{read_many_rel.suffix_key}"
            gen_key = f"{create_key}_gen"
            create_row = CreateRow(
                conn,
                read_many_rel.other_model,
                default_values,
                key=f"{create_key}_{st.session_state.get(gen_key, 0)}",
            )
            ok, msg = create_row.show(pretty_name)
            if ok:
                """New widget keys: the browser keeps a form widget's value when
                only its session state is dropped."""
                create_row.reset_form_state()
                st.session_state[gen_key] = st.session_state.get(gen_key, 0) + 1
            handle_panel_result(create_key, ok, msg)

        with tab_delete:
            delete_key = f"st_sql_many_delete_{read_many_rel.suffix_key}"
            rows_id = df.iloc[rows_pos].index.to_list()
            ok, msg = None, None
            if len(rows_id) == 0:
                st.text("First select the rows to delete")
            else:
                delete_rows = DeleteRows(
                    conn, read_many_rel.other_model, rows_id, delete_key
                )
                ok, msg = delete_rows.show(pretty_name)
            handle_panel_result(delete_key, ok, msg)


def show_rels(
    conn: SessionSource, model: type[DeclarativeBase], model_id: int | str
) -> None:
    """Render a panel for every one-to-many relationship of `model`."""
    rels = [
        rel
        for rel in model.__mapper__.relationships
        if rel.direction is RelationshipDirection.ONETOMANY
    ]

    for rel in rels:
        show_rel(conn, model, model_id, rel)


def handle_panel_result(key: str, ok: bool | None, msg: str | None) -> None:
    """Report the outcome of a panel create/delete with widget key `key`.

    A failure is shown at once, keeping the form; a success reruns the panel
    and shows its message on that rerun.
    """
    notice_key = f"{key}_notice"
    if ok:
        st.session_state[notice_key] = msg
        rerun_panel()
    elif ok is False:
        st.error(msg)
    elif notice_key in st.session_state:
        st.success(st.session_state[notice_key])
        clear_state_keys([notice_key])


def rerun_panel() -> None:
    """Rerun only the panel fragment, so the edit dialog around it stays open.

    A full-app run (first render, AppTest) cannot rerun a fragment: rerun the app.
    """
    ctx = get_script_run_ctx()
    in_fragment_run = ctx is not None and bool(ctx.fragment_ids_this_run)
    st.rerun(scope="fragment" if in_fragment_run else "app")
