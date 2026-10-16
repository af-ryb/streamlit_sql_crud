from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import streamlit as st
from dateutil.relativedelta import relativedelta
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.schema import ForeignKey
from streamlit import session_state as ss

from streamlit_pydantic_crud.lib import CACHE_TTL_SECONDS
from streamlit_pydantic_crud.utils import tablename


def safe_python_type(col: ColumnElement[Any]) -> type | None:
    """Return the column's Python type, or None when the type has none.

    `NullType` (e.g. `literal_column`, untyped `func.*`) and some custom types
    raise NotImplementedError; callers treat such columns as not filterable.
    """
    try:
        return col.type.python_type
    except NotImplementedError:
        return None


@dataclass
class FkOpt:
    idx: int
    name: str


class ExistingData:
    def __init__(
        self,
        session: Session,
        Model: type[DeclarativeBase],
        default_values: dict,
        row: DeclarativeBase | None = None,
        foreign_key_options: dict | None = None,
        dt_filters: dict | None = None,
        no_dt_filters: dict | None = None,
    ) -> None:
        self.session = session
        self.Model = Model
        self.default_values = default_values
        self.row = row
        self.foreign_key_options = foreign_key_options or {}
        self.dt_filters = dt_filters or {}
        self.no_dt_filters = no_dt_filters or {}

        self.cols = Model.__table__.columns
        self._models: list[type[DeclarativeBase]] = [
            mapper.class_ for mapper in Model.registry.mappers
        ]

        table_name = tablename(Model)
        text = self.get_text(table_name, ss.stsql_updated, default_values)
        self.text = self.add_row_values(text)
        self.dt = self.get_dt(table_name, ss.stsql_updated)
        self.fk = self.get_fk()

    def add_default_where(self, stmt, model: type[DeclarativeBase]):
        cols = model.__table__.columns
        default_values = {
            colname: value
            for colname, value in self.default_values.items()
            if colname in cols
        }

        for colname, value in default_values.items():
            default_col = cols.get(colname)
            stmt = stmt.where(default_col == value)

        return stmt

    @st.cache_data(ttl=CACHE_TTL_SECONDS)
    def get_text(
        _self, table_name: str, updated: int, default_values: dict
    ) -> dict[str, Sequence[str]]:
        """Return distinct values of each string column, filtered by defaults.

        Every input of the result is an argument so it is part of the cache key;
        the current row's values are added afterwards by `add_row_values`.
        """
        opts = {
            col.name: _self._get_str_opts(col)
            for col in _self.cols
            if safe_python_type(col) is str
        }
        return opts

    def add_row_values(
        self, text: dict[str, Sequence[str]]
    ) -> dict[str, Sequence[str]]:
        """Return a copy of `text` with the current row's values appended."""
        result: dict[str, Sequence[str]] = {}
        for col_name, opts in text.items():
            row_value = getattr(self.row, col_name, None) if self.row else None
            if row_value is not None and row_value not in opts:
                result[col_name] = [*opts, row_value]
            else:
                result[col_name] = list(opts)
        return result

    def _get_str_opts(self, column) -> Sequence[str]:
        stmt = select(column).distinct().select_from(self.Model).limit(10000)
        stmt = self.add_default_where(stmt, self.Model)
        return list(self.session.execute(stmt).scalars().all())

    def _get_dt_col(self, column):
        min_default = date.today() - relativedelta(days=30)
        min_dt: date = self.session.query(func.min(column)).scalar() or min_default
        max_dt: date = self.session.query(func.max(column)).scalar() or date.today()
        return min_dt, max_dt

    @st.cache_data(ttl=CACHE_TTL_SECONDS)
    def get_dt(_self, table_name: str, updated: int) -> dict[str, tuple[date, date]]:
        opts = {
            col.name: _self._get_dt_col(col)
            for col in _self.cols
            if safe_python_type(col) is date
        }
        return opts

    def get_foreign_opt(self, row, fk_pk_name: str):
        idx = getattr(row, fk_pk_name)
        fk_opt = FkOpt(idx, str(row))
        return fk_opt

    def get_foreign_opts(self, col, foreign_key: ForeignKey) -> list[FkOpt]:
        """Return FK options; only the current value if the target is unmapped."""
        foreign_table_name = foreign_key.column.table.name
        model = next(
            (
                reg
                for reg in self._models
                if getattr(reg, "__tablename__", None) == foreign_table_name
            ),
            None,
        )
        if model is None:
            logger.warning(
                f"No mapped model for table '{foreign_table_name}'; "
                f"offering only the current value for '{col.name}'"
            )
            value = getattr(self.row, col.name, None) if self.row else None
            return [] if value is None else [FkOpt(value, str(value))]
        fk_pk_name = foreign_key.column.description
        stmt = select(model).distinct()

        stmt = self.add_default_where(stmt, model)
        stmt = apply_active_filters(stmt, model, self.dt_filters, self.no_dt_filters)

        rows = self.session.execute(stmt).scalars()

        opts = [self.get_foreign_opt(row, fk_pk_name) for row in rows]

        value = getattr(self.row, col.name, None) if self.row else None
        if value is not None and not any(opt.idx == value for opt in opts):
            target_stmt = select(model).where(foreign_key.column == value)
            target = self.session.execute(target_stmt).scalars().first()
            if target is None:
                opts.append(FkOpt(value, str(value)))
            else:
                opts.append(self.get_foreign_opt(target, fk_pk_name))

        return opts

    def get_fk(self) -> dict[str, list[FkOpt]]:
        """Return FK options per column (uncached: depends on live filters)."""
        fk_cols = [col for col in self.cols if len(list(col.foreign_keys)) > 0]
        opts: dict[str, list[FkOpt]] = {}

        for col in fk_cols:
            if not col.description:
                continue

            col_name = col.description

            if col_name in self.foreign_key_options:
                opts[col_name] = custom_foreign_opts(
                    self.session,
                    col_name,
                    self.foreign_key_options[col_name],
                    row=self.row,
                    dt_filters=self.dt_filters,
                    no_dt_filters=self.no_dt_filters,
                )
            else:
                opts[col_name] = self.get_foreign_opts(
                    col, next(iter(col.foreign_keys))
                )

        return opts


def custom_foreign_opts(
    session: Session,
    col_name: str,
    fk_config: dict,
    row: DeclarativeBase | None = None,
    dt_filters: dict | None = None,
    no_dt_filters: dict | None = None,
) -> list[FkOpt]:
    """Return FK options of a ``foreign_key_options`` entry, narrowed by filters.

    The current value of ``row`` is appended when the filters hide it.
    """
    query = fk_config["query"]
    display_field = fk_config["display_field"]
    value_field = fk_config["value_field"]

    model_class = None
    if hasattr(query, "column_descriptions") and query.column_descriptions:
        model_class = query.column_descriptions[0]["type"]
    elif hasattr(query, "froms") and query.froms:
        model_class = query.froms[0].entity_namespace
    else:
        logger.debug("Could not determine model class from query")

    if model_class:
        query = apply_active_filters(
            query, model_class, dt_filters or {}, no_dt_filters or {}
        )
    else:
        logger.debug("No model class found, skipping filter application")

    opts = [
        FkOpt(getattr(opt_row, value_field), getattr(opt_row, display_field))
        for opt_row in session.execute(query).scalars().all()
    ]

    current_value = getattr(row, col_name, None) if row is not None else None
    if current_value is not None and not any(opt.idx == current_value for opt in opts):
        try:
            if model_class:
                current_row_query = select(model_class).where(
                    getattr(model_class, value_field) == current_value
                )
                current_row = session.execute(current_row_query).scalars().first()
                if current_row:
                    current_display = getattr(current_row, display_field)
                    opts.append(FkOpt(current_value, current_display))
        except Exception:
            """Could not load the display row; fall back to the raw value."""
            logger.exception(
                f"Failed to load display for current FK value of {col_name}"
            )
            opts.append(FkOpt(current_value, str(current_value)))

    return opts


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
