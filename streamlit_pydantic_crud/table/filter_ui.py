"""Filter widgets of the SqlUi "Filter" expander and their cached options."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from loguru import logger
from sqlalchemy import CTE, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum
from streamlit import session_state as ss
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud.helpers.display import display_value, get_pretty_name
from streamlit_pydantic_crud.helpers.sa_model import (
    column_label,
    is_array_type,
    is_json_type,
    safe_python_type,
)
from streamlit_pydantic_crud.state import CACHE_TTL_SECONDS
from streamlit_pydantic_crud.table import params
from streamlit_pydantic_crud.table.query import SQL_HASH_FUNCS, to_date


class ColFilter:
    """Render the filter widgets of the available CTE columns.

    Date columns get a start/end range, others a selectbox of existing values;
    URL query params seed the widgets once.
    """

    def __init__(
        self,
        container: DeltaGenerator,
        cte: CTE,
        existing_values: dict[str, Any],
        available_col_filter: list[str] | None = None,
        key: str = "",
    ) -> None:
        self.container = container
        self.cte = cte
        self.existing_values = existing_values
        self.available_col_filter = available_col_filter or []
        self.key = key
        self.key_prefix = f"{key}_create"

        self.dt_filters = self.get_dt_filters()
        self.no_dt_filters = self.get_no_dt_filters()

    def __str__(self) -> str:
        dt_str = ", ".join(
            f"{k}: {dt.strftime('%d/%m/%Y')}"
            for k, v in self.dt_filters.items()
            for dt in v
            if dt
        )
        no_dt_str = ", ".join(
            f"{k}: {display_value(v)}" for k, v in self.no_dt_filters.items() if v
        )

        filter_str = ""
        if dt_str != "":
            filter_str += f"{dt_str}, "
        if no_dt_str != "":
            filter_str += f"{no_dt_str}"

        return filter_str

    def get_dt_filters(self) -> dict[str, tuple[date | None, date | None]]:
        cols = [
            col
            for col in self.cte.columns
            if column_label(col) in self.available_col_filter
            and safe_python_type(col) is date
        ]

        result: dict[str, tuple[date | None, date | None]] = {}
        for col in cols:
            colname = column_label(col)
            label = get_pretty_name(colname)
            self.container.write(label)
            start_c, end_c, btn_c = self.container.columns(
                [0.475, 0.475, 0.05], vertical_alignment="bottom"
            )

            default_start, default_end = params.get_dt_param(colname, self.key)

            start_key = f"{self.key_prefix}_date_filter_start_{label}"
            end_key = f"{self.key_prefix}_date_filter_end_{label}"
            """The URL only seeds the state: a passed value would stick in the
            browser widget after a cancel."""
            if start_key not in ss:
                ss[start_key] = params.parse_date(default_start)
            if end_key not in ss:
                ss[end_key] = params.parse_date(default_end)

            start = start_c.date_input(
                "Start",
                value=None,
                key=start_key,
                args=(colname, start_key, "start", self.key),
                on_change=params.set_dt_param,
            )

            end = end_c.date_input(
                "End",
                value=None,
                key=end_key,
                args=(colname, end_key, "end", self.key),
                on_change=params.set_dt_param,
            )

            btn_c.button(
                "",
                icon=":material/cancel:",
                key=f"st_sql_{start_key}_{end_key}_cancel_btn",
                on_click=params.clear_filter,
                args=(
                    [start_key, end_key],
                    [
                        params.param_name(self.key, f"{colname}_start"),
                        params.param_name(self.key, f"{colname}_end"),
                    ],
                ),
            )

            start_date = to_date(start)
            end_date = to_date(end)

            result[colname] = start_date, end_date

        return result

    def get_no_dt_filters(self) -> dict[str, Any]:
        cols = [
            col
            for col in self.cte.columns
            if column_label(col) in self.available_col_filter
            and safe_python_type(col) not in (None, date)
        ]

        result: dict[str, Any] = {}
        for col in cols:
            colname = column_label(col)

            existing_value = self.existing_values.get(colname)

            if existing_value is None:
                continue  # Continue to check other columns instead of returning

            label = get_pretty_name(colname)
            key = f"{self.key_prefix}_no_dt_filter_{label}"
            if key not in ss:
                """Seed from the URL once; a computed index would hide the
                native clear button and stick in the browser after a cancel."""
                index = params.get_no_dt_param(col, existing_value, self.key)
                ss[key] = None if index is None else existing_value[index]
            col1, col2 = self.container.columns(
                [0.95, 0.05], vertical_alignment="bottom"
            )
            value = col1.selectbox(
                label,
                options=self.existing_values[colname],
                index=None,
                key=key,
                format_func=display_value,
                args=(colname, key, self.key),
                on_change=params.set_no_dt_param,
            )
            col2.button(
                label="",
                icon=":material/cancel:",
                key=f"{key}_btn",
                on_click=params.clear_filter,
                args=([key], [params.param_name(self.key, colname)]),
            )

            result[colname] = value

        return result


hash_funcs: dict[Any, Callable[[Any], Any]] = {
    pd.Series: lambda serie: serie.to_dict(),
    **SQL_HASH_FUNCS,
    ColFilter: lambda cl: (cl.dt_filters, cl.no_dt_filters),
}
"""st.cache_data hashers; ColFilter is keyed by the class, so moves cannot
silently break it (a string key must match its qualified name)."""


@st.cache_data(hash_funcs=hash_funcs, ttl=CACHE_TTL_SECONDS)
def get_existing_values(
    _session: Session,
    cte: CTE,
    updated: int,
    available_col_filter: list[str] | None = None,
) -> dict[str, Any]:
    """Return the distinct values of each filterable column of `cte`.

    Cached per CTE, `updated` and column list; failing columns are skipped.
    """
    if not available_col_filter:
        available_col_filter = []

    if len(available_col_filter) > 0:
        # Use col.name as fallback if description is None (common for joined columns)
        cols = [
            col
            for col in cte.columns
            if column_label(col) in available_col_filter and get_existing_cond(col)
        ]
    else:
        cols = [col for col in cte.columns if get_existing_cond(col)]

    result: dict[str, Any] = {}
    for col in cols:
        try:
            # For joined columns, we need to select from the CTE itself
            stmt = (
                select(cte.c[col.name])
                .distinct()
                .order_by(cte.c[col.name])
                .limit(10000)
            )
            values = _session.execute(stmt).scalars().all()
            colname = column_label(col)
            result[colname] = values
        except Exception as e:
            # Skip columns that cause errors (like JSON column type)
            colname = column_label(col)
            logger.warning(
                f"Skipping column '{colname}' for filter values due to error: {e}"
            )
            continue

    return result


def get_existing_cond(col: KeyedColumnElement) -> bool:
    """Tell whether `col` gets a selectbox filter fed by distinct values."""
    py_type = safe_python_type(col)
    is_str = py_type is str
    is_bool = py_type is bool
    is_enum = isinstance(col.type, SQLEnum)
    is_not_pk = not col.primary_key

    fks = list(col.foreign_keys)
    has_fk = len(fks) > 0
    int_not_fk_cond = py_type is int and not has_fk

    # Check for JSON column types that don't support SELECT DISTINCT in BigQuery
    col_type_name = str(col.type).upper()
    is_json = is_json_type(col.type)

    # Also check for other unsupported types like ARRAY, STRUCT in BigQuery
    is_unsupported_type = is_array_type(col.type) or any(
        unsupported in col_type_name for unsupported in ("STRUCT", "RECORD")
    )

    cond = (
        is_not_pk
        and not is_json
        and not is_unsupported_type
        and (is_str or is_bool or int_not_fk_cond or is_enum)
    )
    return cond
