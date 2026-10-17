"""Load foreign-key, many-to-many and existing-value options for CRUD forms.

Pydantic forms get options via ``load_form_options``: failures are logged per
field, shown once as an ``st.warning``, and that field falls back to a plain
input. Plain InputFields forms read theirs from ``ExistingData``.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import streamlit as st
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import ForeignKey
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.config_types import (
    ForeignKeyConfig,
    ForeignKeyOptions,
    ManyToManyFields,
)
from streamlit_pydantic_crud.helpers.sa_model import (
    foreign_key_column_names,
    model_by_tablename,
    pk_name,
    related_model,
    safe_python_type,
    tablename,
)
from streamlit_pydantic_crud.state import CACHE_TTL_SECONDS, UPDATED_KEY
from streamlit_pydantic_crud.table.query import apply_active_filters

if TYPE_CHECKING:
    """Type-only: forms sit below pydantic_ui, which imports the form generator."""
    from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi


@dataclass
class FkOpt:
    """One foreign-key option: the referenced id and its display text."""

    idx: int
    name: str


def load_form_options(
    form: "PydanticCrudUi",
    conn: SQLConnection,
    model: type[DeclarativeBase],
    foreign_key_options: ForeignKeyOptions,
    many_to_many_fields: ManyToManyFields,
    row: DeclarativeBase | None = None,
    dt_filters: dict | None = None,
    no_dt_filters: dict | None = None,
) -> None:
    """Fill `form` with the FK and M2M options configured for `model`.

    FK columns of `model` get options narrowed by the page filters, plus the
    current value of `row`; other configured fields run their raw query.
    """
    load_foreign_key_options(
        form, conn, model, foreign_key_options, row, dt_filters, no_dt_filters
    )
    load_many_to_many_options(form, conn, model, many_to_many_fields)


def load_foreign_key_options(
    form: "PydanticCrudUi",
    conn: SQLConnection,
    model: type[DeclarativeBase],
    foreign_key_options: ForeignKeyOptions,
    row: DeclarativeBase | None = None,
    dt_filters: dict | None = None,
    no_dt_filters: dict | None = None,
) -> None:
    """Set the selectbox options of every ``foreign_key_options`` field."""
    fk_columns = foreign_key_column_names(model)
    for field_name, fk_config in foreign_key_options.items():
        try:
            display_field = fk_config["display_field"]
            value_field = fk_config["value_field"]
            with conn.session as session:
                if field_name in fk_columns:
                    fk_opts = custom_foreign_opts(
                        session,
                        field_name,
                        fk_config,
                        row=row,
                        dt_filters=dt_filters,
                        no_dt_filters=no_dt_filters,
                    )
                    options = [
                        {value_field: opt.idx, display_field: opt.name}
                        for opt in fk_opts
                    ]
                else:
                    rows = session.execute(fk_config["query"]).scalars().all()
                    options = [
                        {
                            value_field: getattr(opt_row, value_field),
                            display_field: getattr(opt_row, display_field),
                        }
                        for opt_row in rows
                    ]

            form.input_generator.set_foreign_key_options(
                field_name, options, display_field, value_field
            )
        except Exception:
            """Log and warn; the field falls back to a text input."""
            handle_option_load_error("foreign key", field_name)


def load_many_to_many_options(
    form: "PydanticCrudUi",
    conn: SQLConnection,
    model: type[DeclarativeBase],
    many_to_many_fields: ManyToManyFields,
) -> None:
    """Set the multiselect options of every ``many_to_many_fields`` field."""
    for field_name, m2m_config in many_to_many_fields.items():
        try:
            related = related_model(model, m2m_config["relationship"])
            query = select(related)
            if "filter" in m2m_config:
                query = m2m_config["filter"](query)

            with conn.session as session:
                rows = session.execute(query).scalars().all()
                form.input_generator.set_many_to_many_options(
                    field_name,
                    list(rows),
                    m2m_config["display_field"],
                    pk_name(related),
                )
        except Exception:
            handle_option_load_error("many-to-many", field_name)


def handle_option_load_error(kind: str, field_name: str) -> None:
    """Log the current exception and warn the user about the field.

    Must be called from an ``except`` block. ``kind`` is ``"foreign key"`` or
    ``"many-to-many"``; the warning stays visible even with ``disable_log``.
    """
    logger.exception(f"Failed to load {kind} data for {field_name}")
    st.warning(f"Could not load {kind} options for '{field_name}'.")


class ExistingData:
    """Option values of the plain (non-Pydantic) InputFields of `Model`.

    Distinct strings and FK options, narrowed by the page filters.
    """

    def __init__(
        self,
        session: Session,
        Model: type[DeclarativeBase],
        default_values: dict,
        row: DeclarativeBase | None = None,
        foreign_key_options: ForeignKeyOptions | None = None,
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

        table_name = tablename(Model)
        text = self.get_text(table_name, ss[UPDATED_KEY], default_values)
        self.text = self.add_row_values(text)
        self.fk = self.get_fk()

    def add_default_where(self, stmt, model: type[DeclarativeBase]) -> Any:
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

    def get_foreign_opt(self, row, fk_pk_name: str) -> FkOpt:
        idx = getattr(row, fk_pk_name)
        fk_opt = FkOpt(idx, str(row))
        return fk_opt

    def get_foreign_opts(self, col, foreign_key: ForeignKey) -> list[FkOpt]:
        """Return FK options; only the current value if the target is unmapped."""
        foreign_table_name = foreign_key.column.table.name
        model = model_by_tablename(self.Model, foreign_table_name)
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
    fk_config: ForeignKeyConfig,
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
