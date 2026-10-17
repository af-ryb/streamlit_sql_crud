"""Build and count the SqlUi read statements; no widgets are rendered here.

The read query is wrapped in a CTE, narrowed by the active filters, counted
and paged. ``apply_active_filters`` narrows option queries of related models.
"""

from collections.abc import Callable
from datetime import date
from typing import Any, Protocol

import streamlit as st
from loguru import logger
from sqlalchemy import CTE, Select, func, select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import KeyedColumnElement
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.state import CACHE_TTL_SECONDS

SQL_HASH_FUNCS: dict[Any, Callable[[Any], Any]] = {
    CTE: lambda sel: (str(sel), sel.compile().params),
    Select: lambda sel: (str(sel), sel.compile().params),
}
"""st.cache_data hashers for SQL statements: the SQL text and its params."""


class ActiveFilters(Protocol):
    """The filter values a ``filter_ui.ColFilter`` exposes to the query."""

    @property
    def dt_filters(self) -> dict[str, tuple[date | None, date | None]]:
        """Date range (start, end) per column; either end may be None."""
        ...

    @property
    def no_dt_filters(self) -> dict[str, Any]:
        """Selected value per non-date column; falsy means no filter."""
        ...


def to_cte(read_instance: Select | CTE | type[DeclarativeBase]) -> CTE:
    """Wrap a SqlUi ``read_instance`` (statement, CTE or model) in a CTE."""
    if isinstance(read_instance, Select):
        cte = read_instance.cte()
    elif isinstance(read_instance, CTE):
        cte = read_instance
    else:
        cte = select(read_instance).cte()

    return cte


def get_stmt_no_pag(cte: CTE, col_filter: ActiveFilters) -> Select:
    """Select from `cte` with all filters of `col_filter` applied."""
    stmt = get_stmt_no_pag_dt(cte, col_filter.no_dt_filters)

    for colname, (start, end) in col_filter.dt_filters.items():
        col = find_cte_col(cte, colname)
        if start:
            stmt = stmt.where(col >= start)
        if end:
            stmt = stmt.where(col <= end)

    return stmt


def get_stmt_no_pag_dt(cte: CTE, no_dt_filters: dict[str, Any]) -> Select:
    """Select from `cte` with the non-date filters applied."""
    stmt = select(cte)

    for colname, value in no_dt_filters.items():
        if value:
            stmt = stmt.where(find_cte_col(cte, colname) == value)

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


@st.cache_data(hash_funcs=SQL_HASH_FUNCS, ttl=CACHE_TTL_SECONDS)
def get_qtty_rows(_conn: SQLConnection, stmt_no_pag: Select, version: int) -> int:
    """Count the rows of `stmt_no_pag`; cached per statement and data `version`."""
    stmt = select(func.count()).select_from(stmt_no_pag.subquery())
    with _conn.session as s:
        qtty = s.execute(stmt).scalar_one()

    return qtty


def get_stmt_pag(
    stmt_no_pag: Select,
    limit: int,
    page: int,
    order_by: KeyedColumnElement | None = None,
) -> Select[Any]:
    """Return page `page` (1-based) of `limit` rows of `stmt_no_pag`."""
    offset = (page - 1) * limit
    stmt = stmt_no_pag
    """A deterministic ORDER BY keeps rows from jumping between pages."""
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    stmt = stmt.offset(offset).limit(limit)
    return stmt


def apply_active_filters(
    stmt: Any, model: type[DeclarativeBase], dt_filters: dict, no_dt_filters: dict
) -> Any:
    """Narrow `stmt` by the page filters on columns that `model` also has."""
    for col_name, date_range in dt_filters.items():
        logger.debug(f"Checking date filter: {col_name} on model {model.__name__}")
        if hasattr(model, col_name):
            col = getattr(model, col_name)
            start_date, end_date = date_range
            if start_date:
                stmt = stmt.where(col >= start_date)
            if end_date:
                stmt = stmt.where(col <= end_date)
        else:
            logger.debug(f"Model {model.__name__} does NOT have attribute {col_name}")

    for col_name, value in no_dt_filters.items():
        if value and hasattr(model, col_name):
            col = getattr(model, col_name)
            stmt = stmt.where(col == value)

    return stmt


def to_date(value: object) -> date | None:
    """Return `value` as a plain date, or None if it is not a date."""
    if not isinstance(value, date):
        return None
    return date(value.year, value.month, value.day)
