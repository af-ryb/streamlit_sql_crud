"""The delete dialog: preview the selected rows and delete them."""

from functools import partial

import streamlit as st
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.db_errors import format_database_error
from streamlit_pydantic_crud.dialogs.frame import show_crud_dialog
from streamlit_pydantic_crud.display import get_pretty_name
from streamlit_pydantic_crud.logs import log
from streamlit_pydantic_crud.sa_model import pk_column, tablename
from streamlit_pydantic_crud.state import CACHE_TTL_SECONDS, UPDATED_KEY


class DeleteRows:
    """Delete dialog for the rows `rows_id` of `model`."""

    def __init__(
        self,
        conn: SQLConnection,
        model: type[DeclarativeBase],
        rows_id: list[int],
        key: str,
    ) -> None:
        self.conn = conn
        self.model = model
        self.rows_id = rows_id
        self.key = key
        self.key_prefix = f"{key}_delete"

    @st.cache_data(ttl=CACHE_TTL_SECONDS)
    def get_rows_str(
        _self, table_name: str, rows_id: list[int], updated: int
    ) -> list[str]:
        """Return the string form of the rows to delete.

        `table_name` and the `updated` counter are cache-key inputs only.
        """
        id_col = pk_column(_self.model)
        stmt = select(_self.model).where(id_col.in_(rows_id))

        with _self.conn.session as s:
            rows = s.execute(stmt).scalars()
            rows_str = [str(row) for row in rows]

        return rows_str

    def show(self, pretty_name) -> tuple[bool | None, str | None]:
        st.subheader("Delete selected items?")

        table_name = tablename(self.model)
        updated = ss.get(UPDATED_KEY, 0)
        rows_str = self.get_rows_str(table_name, self.rows_id, updated)
        st.dataframe({pretty_name: rows_str}, hide_index=True)

        btn = st.button("Delete", key=f"{self.key_prefix}_del_btn")
        if not btn:
            return None, None

        lancs: list[str] = []
        missing: list[int] = []
        with self.conn.session as s:
            try:
                for row_id in self.rows_id:
                    lanc = s.get(self.model, row_id)
                    if lanc is None:
                        missing.append(row_id)
                        continue
                    lancs.append(str(lanc))
                    s.delete(lanc)

                s.commit()
                ss[UPDATED_KEY] += 1
            except Exception as e:
                ss[UPDATED_KEY] += 1
                log("DELETE", table_name, self.rows_id, success=False)
                logger.exception(f"Delete failed for {table_name}")
                return False, format_database_error(e)

        missing_msg = f"Not found (already deleted?): {missing}" if missing else ""
        if not lancs:
            return False, missing_msg

        log("DELETE", table_name, ", ".join(lancs))
        msg = f"Successfully deleted {len(lancs)}"
        return True, f"{msg}. {missing_msg}" if missing else msg

    def show_dialog(self) -> None:
        """Open the delete dialog."""
        pretty_name = get_pretty_name(tablename(self.model))
        show_crud_dialog(
            f"Delete {pretty_name}", self.key, partial(self.show, pretty_name)
        )
