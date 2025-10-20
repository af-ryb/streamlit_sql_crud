from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
import streamlit_antd_components as sac
from sqlalchemy import CTE, Select, distinct, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud import params
from streamlit_pydantic_crud.lib import get_pretty_name
from loguru import logger


hash_funcs: dict[Any, Callable[[Any], Any]] = {
    pd.Series: lambda serie: serie.to_dict(),
    CTE: lambda sel: (str(sel), sel.compile().params),
    Select: lambda sel: (str(sel), sel.compile().params),
    "streamlit_pydantic_crud.read_cte.ColFilter": lambda cl: (cl.dt_filters, cl.no_dt_filters),
}


def get_existing_cond(col: KeyedColumnElement):
    is_str = col.type.python_type is str
    is_bool = col.type.python_type is bool
    is_enum = isinstance(col.type, SQLEnum)
    is_not_pk = not col.primary_key

    fks = list(col.foreign_keys)
    has_fk = len(fks) > 0
    int_not_fk_cond = col.type.python_type is int and not has_fk
    
    # Check for JSON column types that don't support SELECT DISTINCT in BigQuery
    is_json_type = False
    col_type_name = str(col.type).upper()
    if 'JSON' in col_type_name or hasattr(col.type, '__class__') and 'JSON' in col.type.__class__.__name__.upper():
        is_json_type = True
    
    # Also check for other unsupported types like ARRAY, STRUCT in BigQuery
    unsupported_types = ['ARRAY', 'STRUCT', 'RECORD']
    is_unsupported_type = any(unsupported in col_type_name for unsupported in unsupported_types)

    cond = is_not_pk and not is_json_type and not is_unsupported_type and (is_str or is_bool or int_not_fk_cond or is_enum)
    return cond


@st.cache_data(hash_funcs=hash_funcs)
def get_existing_values(
    _session: Session,
    cte: CTE,
    updated: int,
    available_col_filter: list[str] | None = None,
):
    if not available_col_filter:
        available_col_filter = []

    cols = list(cte.columns)

    if len(available_col_filter) > 0:
        # Use col.name as fallback if description is None (common for joined columns)
        cols = [col for col in cte.columns if (col.description or col.name) in available_col_filter and get_existing_cond(col)]
    else:
        cols = [col for col in cte.columns if get_existing_cond(col)]

    result: dict[str, Any] = {}
    for col in cols:
        try:
            # For joined columns, we need to select from the CTE itself
            stmt = select(distinct(cte.c[col.name])).order_by(cte.c[col.name]).limit(10000)
            values = _session.execute(stmt).scalars().all()
            # Use col.name if description is None (common for joined columns)
            colname = col.description or col.name
            result[colname] = values
        except Exception as e:
            # Skip columns that cause errors (like JSON column type)
            colname = col.description or col.name
            logger.warning(f"Skipping column '{colname}' for filter values due to error: {e}")
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
        self.key_prefix = f"{key}_create"


        self.dt_filters = self.get_dt_filters()
        self.no_dt_filters = self.get_no_dt_filters()
        

    def __str__(self):
        dt_str = ", ".join(
            f"{k}: {dt.strftime('%d/%m/%Y')}"
            for k, v in self.dt_filters.items()
            for dt in v
            if v
            if dt
        )
        no_dt_str = ", ".join(f"{k}: {v}" for k, v in self.no_dt_filters.items() if v)

        filter_str = ""
        if dt_str != "":
            filter_str += f"{dt_str}, "
        if no_dt_str != "":
            filter_str += f"{no_dt_str}"

        return filter_str

    def get_dt_filters(self):
        cols = [
            col
            for col in self.cte.columns
            if (col.description or col.name) in self.available_col_filter
            and col.type.python_type is date
        ]

        result: dict[str, tuple[date | None, date | None]] = {}
        for col in cols:
            # Use col.name as fallback for joined columns
            colname = col.description or col.name
            label = get_pretty_name(colname)
            self.container.write(label)
            inicio_c, final_c, btn_c = self.container.columns(
                [0.475, 0.475, 0.05], vertical_alignment="bottom"
            )

            default_inicio, default_final = params.get_dt_param(colname)

            inicio_key = f"{self.key_prefix}_date_filter_inicio_{label}"
            inicio = inicio_c.date_input(
                "Inicio",
                value=default_inicio,
                key=inicio_key,
                args=(colname, inicio_key, "inicio"),
                on_change=params.set_dt_param,
            )

            final_key = f"{self.key_prefix}_date_filter_final_{label}"
            final = final_c.date_input(
                "Final",
                value=default_final,
                key=final_key,
                args=(colname, final_key, "final"),
                on_change=params.set_dt_param,
            )

            btn = btn_c.button(
                "",
                icon=":material/cancel:",
                key=f"st_sql_{inicio_key}_{final_key}_cancel_btn",
            )
            if btn:
                st.query_params.pop(f"{colname}_inicio", None)
                st.query_params.pop(f"{colname}_final", None)
                st.rerun()

            assert inicio is None or isinstance(inicio, date)
            if inicio is None:
                inicio_date = None
            else:
                inicio_date = date(inicio.year, inicio.month, inicio.day)

            assert final is None or isinstance(final, date)
            if final is None:
                final_date = None
            else:
                final_date = date(final.year, final.month, final.day)

            result[colname] = inicio_date, final_date

        return result

    def get_no_dt_filters(self):
        cols = [
            col
            for col in self.cte.columns
            if (col.description or col.name) in self.available_col_filter
            and col.type.python_type is not date
        ]

        result: dict[str, Any] = {}
        for col in cols:
            # Use col.name as fallback for joined columns
            colname = col.description or col.name

            existing_value = self.existing_values.get(colname)

            if existing_value is None:
                continue  # Continue to check other columns instead of returning

            label = get_pretty_name(colname)
            key = f"{self.key_prefix}_no_dt_filter_{label}"
            index = params.get_no_dt_param(col, existing_value)
            col1, col2 = self.container.columns(
                [0.95, 0.05], vertical_alignment="bottom"
            )
            value = col1.selectbox(
                label,
                options=self.existing_values[colname],
                index=index,
                key=key,
                args=(colname, key),
                on_change=params.set_no_dt_param,
            )
            btn = col2.button(label="", icon=":material/cancel:", key=f"{key}_btn")
            if btn:
                st.query_params.pop(colname, None)
                st.rerun()

            result[colname] = value

        return result


def get_stmt_no_pag_dt(cte: CTE, no_dt_filters: dict[str, str | None]):
    stmt = select(cte)
    
    for colname, value in no_dt_filters.items():
        if value:
            # First try to get by description, then by name
            col = None
            for c in cte.columns:
                if c.description == colname or c.name == colname:
                    col = c
                    break
            
            if col is not None:
                stmt = stmt.where(col == value)
            else:
                assert col is not None, f"Column '{colname}' not found in CTE"

    return stmt


def get_stmt_no_pag(cte: CTE, col_filter: ColFilter):
    no_dt_filters = col_filter.no_dt_filters
    stmt = get_stmt_no_pag_dt(cte, no_dt_filters)

    dt_filters = col_filter.dt_filters
    for colname, filters in dt_filters.items():
        # First try to get by description, then by name
        col = None
        for c in cte.columns:
            if c.description == colname or c.name == colname:
                col = c
                break
        assert col is not None
        inicio, final = filters
        if inicio:
            stmt = stmt.where(col >= inicio)
        if final:
            stmt = stmt.where(col <= final)

    return stmt


@st.cache_data(hash_funcs=hash_funcs)
def get_qtty_rows(_conn: SQLConnection, stmt_no_pag: Select, updated: int):
    stmt = select(func.count()).select_from(stmt_no_pag.subquery())
    with _conn.session as s:
        qtty = s.execute(stmt).scalar_one()

    return qtty


def show_pagination(count: int, opts_items_page: tuple[int | None, ...], key: str = "", default_index: int | None = None):
    pag_col1, pag_col2 = st.columns([0.2, 0.8])

    # Convert options to strings, replacing None with "Show All"
    items_page_display = []
    for item in opts_items_page:
        if item is None:
            items_page_display.append("Show All")
        else:
            items_page_display.append(str(item))

    # Initialize session state for cascader if not exists
    cascader_key = f"{key}_menu_cascader"
    if cascader_key not in st.session_state and default_index is not None:
        # Set initial value in session state based on default_index
        if default_index < len(items_page_display):
            st.session_state[cascader_key] = [items_page_display[default_index]]

    # Determine default value
    if default_index is not None and default_index < len(items_page_display):
        default_value = items_page_display[default_index]
    else:
        default_value = items_page_display[0] if items_page_display else "50"

    with pag_col1:
        menu_cas = sac.cascader(
            items=items_page_display,  # pyright: ignore
            placeholder="Items per page",
            index=default_index if default_index is not None else 0,
            key=cascader_key,
        )

    # Get selected value
    selected_str = menu_cas[0] if menu_cas else default_value

    # Map back to actual value (None for "Show All", otherwise int)
    if selected_str == "Show All":
        items_per_page = count  # Show all items
    else:
        items_per_page = int(selected_str)

    with pag_col2:
        page = sac.pagination(
            total=count,
            page_size=items_per_page,
            show_total=True,
            jump=True,
            key=f"{key}_pagination",
        )

    return (items_per_page, int(page))


def get_stmt_pag(stmt_no_pag: Select, limit: int, page: int):
    offset = (page - 1) * limit
    stmt = stmt_no_pag.offset(offset).limit(limit)
    
    
    return stmt


# @st.cache_data(hash_funcs=hash_funcs)
def initial_balance(
    _session: Session,
    stmt_no_pag_dt: Select,
    stmt_pag: Select,
    rolling_total_column: str,
    orderby_cols: list,
) -> float:
    stmt_pag_ordered = stmt_pag.order_by(*orderby_cols)
    first_pag = _session.execute(stmt_pag_ordered).first()
    if not first_pag:
        return 0

    stmt_no_pag_dt_ordered = stmt_no_pag_dt.order_by(*orderby_cols)
    for col in orderby_cols:
        stmt_no_pag_dt_ordered = stmt_no_pag_dt_ordered.where(
            col < getattr(first_pag, col.name)
        )

    stmt_bal = select(func.sum(stmt_no_pag_dt_ordered.c.get(rolling_total_column)))
    bal = _session.execute(stmt_bal).scalar_one() or 0
    return bal
