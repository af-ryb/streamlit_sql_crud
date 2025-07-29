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
    
    # DEBUG: Log available CTE columns
    cte_column_names = [col.description or col.name for col in cols]
    logger.debug(f"get_existing_values: Available CTE columns: {cte_column_names}")
    logger.debug(f"get_existing_values: Requested filter columns: {available_col_filter}")

    if len(available_col_filter) > 0:
        # Use col.name as fallback if description is None (common for joined columns)
        matching_cols = [col for col in cte.columns if (col.description or col.name) in available_col_filter and get_existing_cond(col)]
        matching_names = [col.description or col.name for col in matching_cols]
        logger.debug(f"get_existing_values: Matching filter columns: {matching_names}")
        cols = matching_cols
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

        # DEBUG: Log filter column discovery
        cte_column_names = [col.description or col.name for col in self.cte.columns]
        logger.debug(f"ColFilter.__init__: Available CTE columns: {cte_column_names}")
        logger.debug(f"ColFilter.__init__: Requested filter columns: {self.available_col_filter}")

        self.dt_filters = self.get_dt_filters()
        self.no_dt_filters = self.get_no_dt_filters()
        
        # DEBUG: Log what filters were actually created
        logger.debug(f"ColFilter.__init__: Created dt_filters: {list(self.dt_filters.keys())}")
        logger.debug(f"ColFilter.__init__: Created no_dt_filters: {list(self.no_dt_filters.keys())}")

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
    
    logger.debug(f"get_stmt_no_pag_dt: Applying filters: {no_dt_filters}")
    cte_column_names = [col.description or col.name for col in cte.columns]
    logger.debug(f"get_stmt_no_pag_dt: Available CTE columns: {cte_column_names}")
    
    for colname, value in no_dt_filters.items():
        if value:
            # First try to get by description, then by name
            col = None
            for c in cte.columns:
                if c.description == colname or c.name == colname:
                    col = c
                    break
            
            if col is not None:
                logger.debug(f"get_stmt_no_pag_dt: Found column '{colname}', applying filter: {colname} == {value}")
                stmt = stmt.where(col == value)
            else:
                logger.error(f"get_stmt_no_pag_dt: Column '{colname}' not found in CTE columns: {cte_column_names}")
                # Don't assert here to see what happens, just log the error
                # assert col is not None

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
def get_qtty_rows(_conn: SQLConnection, stmt_no_pag: Select):
    stmt = select(func.count()).select_from(stmt_no_pag.subquery())
    with _conn.session as s:
        qtty = s.execute(stmt).scalar_one()

    return qtty


def show_pagination(count: int, opts_items_page: tuple[int, ...], key: str = ""):
    pag_col1, pag_col2 = st.columns([0.2, 0.8])

    first_item_candidates = [item for item in opts_items_page if item > count]
    last_item = (
        first_item_candidates[0] if opts_items_page[-1] > count else opts_items_page[-1]
    )
    items_page_str = [str(item) for item in opts_items_page if item <= last_item]

    with pag_col1:
        menu_cas = sac.cascader(
            items=items_page_str,  # pyright: ignore
            placeholder="Items per page",
            key=f"{key}_menu_cascader",
        )

    items_per_page = menu_cas[0] if menu_cas else items_page_str[0]

    with pag_col2:
        page = sac.pagination(
            total=count,
            page_size=int(items_per_page),
            show_total=True,
            jump=True,
            key=f"{key}_pagination",
        )

    return (int(items_per_page), int(page))


def get_stmt_pag(stmt_no_pag: Select, limit: int, page: int):
    offset = (page - 1) * limit
    stmt = stmt_no_pag.offset(offset).limit(limit)
    
    # DEBUG: Log final paginated statement
    logger.debug(f"get_stmt_pag: Final paginated statement: {stmt}")
    logger.debug(f"get_stmt_pag: limit={limit}, page={page}, offset={offset}")
    
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
