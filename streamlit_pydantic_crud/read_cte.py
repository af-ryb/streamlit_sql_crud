from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
import streamlit_antd_components as sac
from loguru import logger
from sqlalchemy import CTE, Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud import params
from streamlit_pydantic_crud.lib import CACHE_TTL_SECONDS, get_pretty_name
from streamlit_pydantic_crud.sa_model import (
    column_label,
    is_array_type,
    is_json_type,
    safe_python_type,
)

SHOW_ALL = "Show All"

hash_funcs: dict[Any, Callable[[Any], Any]] = {
    pd.Series: lambda serie: serie.to_dict(),
    CTE: lambda sel: (str(sel), sel.compile().params),
    Select: lambda sel: (str(sel), sel.compile().params),
    "streamlit_pydantic_crud.read_cte.ColFilter": lambda cl: (
        cl.dt_filters,
        cl.no_dt_filters,
    ),
}


def get_existing_cond(col: KeyedColumnElement) -> bool:
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


@st.cache_data(hash_funcs=hash_funcs, ttl=CACHE_TTL_SECONDS)
def get_existing_values(
    _session: Session,
    cte: CTE,
    updated: int,
    available_col_filter: list[str] | None = None,
) -> dict[str, Any]:
    if not available_col_filter:
        available_col_filter = []

    cols = list(cte.columns)

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


class ColFilter:
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
            f"{k}: {params.display_value(v)}"
            for k, v in self.no_dt_filters.items()
            if v
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
                format_func=params.display_value,
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


def to_date(value: object) -> date | None:
    """Return `value` as a plain date, or None if it is not a date."""
    if not isinstance(value, date):
        return None
    return date(value.year, value.month, value.day)


def get_stmt_no_pag_dt(cte: CTE, no_dt_filters: dict[str, Any]) -> Select:
    """Select from `cte` with the non-date filters applied."""
    stmt = select(cte)

    for colname, value in no_dt_filters.items():
        if value:
            stmt = stmt.where(find_cte_col(cte, colname) == value)

    return stmt


def get_stmt_no_pag(cte: CTE, col_filter: ColFilter) -> Select:
    """Select from `cte` with all filters of `col_filter` applied."""
    stmt = get_stmt_no_pag_dt(cte, col_filter.no_dt_filters)

    for colname, (start, end) in col_filter.dt_filters.items():
        col = find_cte_col(cte, colname)
        if start:
            stmt = stmt.where(col >= start)
        if end:
            stmt = stmt.where(col <= end)

    return stmt


def find_cte_col(cte: CTE, colname: str) -> KeyedColumnElement:
    """Return the CTE column matching `colname` by description, then name.

    Raises ValueError when the CTE has no such column.
    """
    for c in cte.columns:
        if c.description == colname or c.name == colname:
            return c
    msg = f"Filter column '{colname}' not found in the read query"
    raise ValueError(msg)


@st.cache_data(hash_funcs=hash_funcs, ttl=CACHE_TTL_SECONDS)
def get_qtty_rows(_conn: SQLConnection, stmt_no_pag: Select, updated: int) -> int:
    stmt = select(func.count()).select_from(stmt_no_pag.subquery())
    with _conn.session as s:
        qtty = s.execute(stmt).scalar_one()

    return qtty


def pagination_widget_key(key: str, items_per_page: int, count: int) -> str:
    """Build a pagination widget key that encodes page size and total.

    sac.pagination caches these in frontend state on mount, so changing the
    key forces a remount that picks up the new page size and total.
    """
    return f"{key}_pagination_{items_per_page}_{count}"


def show_pagination(
    count: int,
    opts_items_page: tuple[int | None, ...],
    key: str = "",
    default_index: int = 0,
) -> tuple[int, int]:
    pag_col1, pag_col2 = st.columns([0.2, 0.8])

    # Convert options to strings, replacing None with "Show All"
    items_page_display: list[str] = []
    for item in opts_items_page:
        if item is None:
            items_page_display.append(SHOW_ALL)
        else:
            items_page_display.append(str(item))

    # Initialize session state for cascader if not exists
    cascader_key = f"{key}_menu_cascader"
    if cascader_key not in st.session_state and default_index < len(items_page_display):
        # Set initial value in session state based on default_index
        st.session_state[cascader_key] = [items_page_display[default_index]]

    # Determine default value
    if default_index < len(items_page_display):
        default_value = items_page_display[default_index]
    else:
        default_value = items_page_display[0] if items_page_display else "50"

    """sac.cascader expects a list of str | dict | CasItem (list is invariant)."""
    cascader_items: list[str | dict | sac.CasItem] = list(items_page_display)
    with pag_col1:
        menu_cas = sac.cascader(
            items=cascader_items,
            placeholder="Items per page",
            index=default_index,
            key=cascader_key,
        )

    # Get selected value
    selected_str = menu_cas[0] if menu_cas else default_value

    items_per_page = resolve_page_size(selected_str, count)

    # Key encodes page size and total so the widget remounts (and resets to
    # page 1) when either changes, picking up the new page-count display.
    pagination_key = pagination_widget_key(key, items_per_page, count)

    with pag_col2:
        page = sac.pagination(
            total=count,
            page_size=items_per_page,
            show_total=True,
            jump=True,
            key=pagination_key,
        )

    return (items_per_page, int(page))


def resolve_page_size(selected: str | int, count: int) -> int:
    """Map a page-size option to rows per page; "Show All" means all rows.

    Never 0: the pagination frontend divides the total by the page size.
    """
    if selected == SHOW_ALL:
        return max(count, 1)
    return int(selected)


def get_stmt_pag(
    stmt_no_pag: Select,
    limit: int,
    page: int,
    order_by: KeyedColumnElement | None = None,
) -> Select[Any]:
    offset = (page - 1) * limit
    stmt = stmt_no_pag
    # A deterministic ORDER BY keeps rows from jumping between pages.
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    stmt = stmt.offset(offset).limit(limit)
    return stmt
