"""Build and count the SqlUi read statements; no widgets are rendered here.

The read query is wrapped in a CTE, narrowed by the active filters, counted
and paged. ``apply_active_filters`` narrows option queries of related models.
"""

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, Protocol

import streamlit as st
from loguru import logger
from sqlalchemy import CTE, Select, func, select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import (
    ColumnElement,
    KeyedColumnElement,
    UnaryExpression,
    _label_reference,
    _textual_label_reference,
)

from streamlit_pydantic_crud.config_types import MappedModel, SessionSource
from streamlit_pydantic_crud.state import CACHE_TTL_SECONDS

SQL_HASH_FUNCS: dict[Any, Callable[[Any], Any]] = {
    CTE: lambda sel: (str(sel), sel.compile().params),
    Select: lambda sel: (str(sel), sel.compile().params),
}
"""st.cache_data hashers for SQL statements: the SQL text and its params."""

ORDER_LABEL_PREFIX = "_stsql_order_"
"""Label prefix of the hidden CTE columns carrying the read query's ORDER BY."""

ORDER_MODIFIERS: dict[Any, Callable[[Any], ColumnElement[Any]]] = {
    operators.desc_op: lambda col: col.desc(),
    operators.asc_op: lambda col: col.asc(),
    operators.nulls_first_op: lambda col: col.nulls_first(),
    operators.nulls_last_op: lambda col: col.nulls_last(),
}
"""ORDER BY modifiers re-applied to the outer query's order columns."""


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


def to_cte(read_instance: Select | CTE | type[MappedModel]) -> CTE:
    """Wrap a SqlUi ``read_instance`` (statement, CTE or model) in a CTE.

    A statement's ORDER BY expressions that are not selected become hidden
    columns (`ORDER_LABEL_PREFIX`), so the paged outer query can order by them.
    """
    if isinstance(read_instance, Select):
        cte = with_order_columns(read_instance).cte()
    elif isinstance(read_instance, CTE):
        cte = read_instance
    else:
        cte = select(read_instance).cte()

    return cte


def paging_order(
    read_instance: Select | CTE | type[MappedModel],
    cte: CTE,
    pk_col: KeyedColumnElement[Any] | None,
) -> list[ColumnElement[Any]]:
    """Return the outer ORDER BY of `cte`: the statement's order, then the PK.

    The PK tiebreak keeps pages stable; it is skipped when already ordered by.
    A CTE or model `read_instance` has no order of its own: PK order only.
    """
    order: list[ColumnElement[Any]] = []
    ordered_cols: list[ColumnElement[Any]] = []
    if isinstance(read_instance, Select):
        for i, (base, modifiers) in enumerate(order_terms(read_instance)):
            col = cte_order_column(cte, base, i)
            if col is None:
                continue
            ordered_cols.append(col)
            for modifier in reversed(modifiers):
                col = ORDER_MODIFIERS[modifier](col)
            order.append(col)
    if pk_col is not None and not any(c is pk_col for c in ordered_cols):
        order.append(pk_col)
    return order


def visible_columns(cte: CTE) -> list[KeyedColumnElement[Any]]:
    """Return the columns of `cte` without the hidden ORDER BY ones."""
    return [c for c in cte.columns if not c.key.startswith(ORDER_LABEL_PREFIX)]


def with_order_columns(stmt: Select) -> Select:
    """Add each unselected ORDER BY expression of `stmt` as a hidden column.

    The inner ORDER BY is dropped (the outer query orders) unless a LIMIT or
    OFFSET makes it choose the rows.
    """
    terms = order_terms(stmt)
    if not terms:
        return stmt
    hidden = [
        base.label(f"{ORDER_LABEL_PREFIX}{i}")
        for i, (base, _) in enumerate(terms)
        if isinstance(base, ColumnElement)
        and stmt.selected_columns.corresponding_column(base) is None
    ]
    if not has_row_limit(stmt):
        stmt = stmt.order_by(None)
    return stmt.add_columns(*hidden)


def cte_order_column(
    cte: CTE, base: ColumnElement[Any] | str, index: int
) -> ColumnElement[Any] | None:
    """Return the CTE column holding ORDER BY term `index` of value `base`."""
    if isinstance(base, str):
        return cte.c.get(base)
    hidden = cte.c.get(f"{ORDER_LABEL_PREFIX}{index}")
    if hidden is not None:
        return hidden
    return cte.c.corresponding_column(base)


def order_terms(stmt: Select) -> list[tuple[ColumnElement[Any] | str, list[Any]]]:
    """Split each ORDER BY clause of `stmt` into (expression, modifiers).

    Modifiers (desc, nulls_last, ...) are listed outermost first; a string is
    a textual label reference. Raw ``text()`` clauses cannot be lifted: skipped.
    """
    terms: list[tuple[ColumnElement[Any] | str, list[Any]]] = []
    """SQLAlchemy 2.0 has no public accessor for a Select's ORDER BY clauses."""
    for clause in stmt._order_by_clauses:
        modifiers = []
        element: Any = clause
        while (
            isinstance(element, UnaryExpression) and element.modifier in ORDER_MODIFIERS
        ):
            modifiers.append(element.modifier)
            element = element.element
        if isinstance(element, _textual_label_reference | _label_reference):
            terms.append((element.element, modifiers))
        elif isinstance(element, ColumnElement):
            terms.append((element, modifiers))
        else:
            logger.warning(f"Ignoring ORDER BY clause {element} of the read query")
    return terms


def has_row_limit(stmt: Select) -> bool:
    """Return True when `stmt` has a LIMIT, OFFSET or FETCH clause."""
    return (
        stmt._limit_clause is not None
        or stmt._offset_clause is not None
        or stmt._fetch_clause is not None
    )


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
    """Select the visible columns of `cte` with the non-date filters applied."""
    stmt = select(*visible_columns(cte))

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
def get_qtty_rows(_conn: SessionSource, stmt_no_pag: Select, version: int) -> int:
    """Count the rows of `stmt_no_pag`; cached per statement and data `version`."""
    stmt = select(func.count()).select_from(stmt_no_pag.subquery())
    with _conn.session as s:
        qtty = s.execute(stmt).scalar_one()

    return qtty


def get_stmt_pag(
    stmt_no_pag: Select,
    limit: int,
    page: int,
    order_by: Sequence[ColumnElement[Any]] = (),
) -> Select[Any]:
    """Return page `page` (1-based) of `limit` rows of `stmt_no_pag`."""
    offset = (page - 1) * limit
    stmt = stmt_no_pag
    """A deterministic ORDER BY keeps rows from jumping between pages."""
    if order_by:
        stmt = stmt.order_by(*order_by)
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
