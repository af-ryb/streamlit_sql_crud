
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import streamlit as st
from dateutil.relativedelta import relativedelta
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import ForeignKey
from streamlit import session_state as ss
from loguru import logger

@dataclass
class FkOpt:
    idx: int
    name: str


class ExistingData:
    def __init__(self,
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
        reg_values: Any = Model.registry._class_registry.values()
        self._models = [reg for reg in reg_values if hasattr(reg, "__tablename__")]

        table_name = Model.__tablename__
        self.text = self.get_text(table_name, ss.stsql_updated)
        self.dt = self.get_dt(table_name, ss.stsql_updated)
        self.fk = self.get_fk(table_name, ss.stsql_updated)

    def apply_active_filters(self, stmt, model: type[DeclarativeBase]):
        from loguru import logger
        
        # logger.debug(f"apply_active_filters called for model: {model.__name__}")
        # logger.debug(f"dt_filters: {self.dt_filters}")
        # logger.debug(f"no_dt_filters: {self.no_dt_filters}")
        
        # Apply date filters
        for col_name, date_range in self.dt_filters.items():
            logger.debug(f"Checking date filter: {col_name} on model {model.__name__}")
            if hasattr(model, col_name):
                # logger.debug(f"Model {model.__name__} has attribute {col_name} - applying date filter")
                col = getattr(model, col_name)
                start_date, end_date = date_range
                if start_date:
                    stmt = stmt.where(col >= start_date)
                if end_date:
                    stmt = stmt.where(col <= end_date)
            else:
                logger.debug(f"Model {model.__name__} does NOT have attribute {col_name}")

        # Apply non-date filters
        for col_name, value in self.no_dt_filters.items():
            # logger.debug(f"Checking non-date filter: {col_name} = {value} on model {model.__name__}")
            if value and hasattr(model, col_name):
                # logger.debug(f"Model {model.__name__} has attribute {col_name} - applying filter: {col_name} = {value}")
                col = getattr(model, col_name)
                stmt = stmt.where(col == value)

        return stmt

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

    def _get_str_opts(self, column) -> Sequence[str]:
        col_name = column.name
        stmt = select(distinct(column)).select_from(self.Model).limit(10000)
        stmt = self.add_default_where(stmt, self.Model)

        opts = list(self.session.execute(stmt).scalars().all())
        row_value = None
        if self.row:
            row_value: str | None = getattr(self.row, col_name)
        if row_value is not None and row_value not in opts:
            opts.append(row_value)

        return opts

    @st.cache_data
    def get_text(_self, table_name: str, updated: int) -> dict[str, Sequence[str]]:
        opts = {
            col.name: _self._get_str_opts(col)
            for col in _self.cols
            if col.type.python_type is str
        }
        return opts

    def _get_dt_col(self, column):
        min_default = date.today() - relativedelta(days=30)
        min_dt: date = self.session.query(func.min(column)).scalar() or min_default
        max_dt: date = self.session.query(func.max(column)).scalar() or date.today()
        return min_dt, max_dt

    @st.cache_data
    def get_dt(_self, table_name: str, updated: int) -> dict[str, tuple[date, date]]:
        opts = {
            col.name: _self._get_dt_col(col)
            for col in _self.cols
            if col.type.python_type is date
        }
        return opts

    def get_foreign_opt(self, row, fk_pk_name: str):
        idx = getattr(row, fk_pk_name)
        fk_opt = FkOpt(idx, str(row))
        return fk_opt

    def get_foreign_opts(self, col, foreign_key: ForeignKey):
        foreign_table_name = foreign_key.column.table.name
        model = next(
            reg for reg in self._models if reg.__tablename__ == foreign_table_name
        )
        fk_pk_name = foreign_key.column.description
        stmt = select(model).distinct()

        stmt = self.add_default_where(stmt, model)
        stmt = self.apply_active_filters(stmt, model)

        rows = self.session.execute(stmt).scalars()

        opts = [self.get_foreign_opt(row, fk_pk_name) for row in rows]

        opt_row = None
        if self.row is not None:
            opt_row = self.get_foreign_opt(self.row, fk_pk_name)
        if opt_row and opt_row not in opts:
            opts.append(opt_row)

        return opts

    def get_custom_foreign_opts(self, col_name: str, fk_config: dict):
        """Get foreign key options using custom configuration"""
        # logger.debug(f"get_custom_foreign_opts called for col_name: {col_name}")
        # logger.debug(f"fk_config: {fk_config}")
        
        query = fk_config['query']
        display_field = fk_config['display_field']
        value_field = fk_config['value_field']
        
        # logger.debug(f"Original query: {query}")

        model_class = None
        if hasattr(query, 'column_descriptions') and query.column_descriptions:
            model_class = query.column_descriptions[0]['type']
        elif hasattr(query, 'froms') and query.froms:
            model_class = query.froms[0].entity_namespace
        else:
            logger.debug("Could not determine model class from query")
        
        if model_class:
            # logger.debug(f"Applying active filters to query for model: {model_class}")
            filtered_query = self.apply_active_filters(query, model_class)
            # logger.debug(f"Query after filters: {filtered_query}")
            query = filtered_query
        else:
            logger.debug("No model class found, skipping filter application")
        
        # Execute query to get rows
        # logger.debug("Executing query to get foreign key options")
        rows = self.session.execute(query).scalars().all()
        # logger.debug(f"Query returned {len(rows)} rows: {[str(row) for row in rows]}")
        
        # Create FkOpt objects with custom display and value fields
        opts = []
        for row in rows:
            value = getattr(row, value_field)
            display = getattr(row, display_field)
            opts.append(FkOpt(value, display))
        
        # Add current row value if it exists and not in options
        if self.row is not None:
            current_value = getattr(self.row, col_name, None)
            if current_value is not None:
                if not any(opt.idx == current_value for opt in opts):
                    try:
                        if model_class:
                            current_row_query = select(model_class).where(getattr(model_class, value_field) == current_value)
                            current_row = self.session.execute(current_row_query).scalars().first()
                            if current_row:
                                current_display = getattr(current_row, display_field)
                                opts.append(FkOpt(current_value, current_display))
                    except Exception:
                        opts.append(FkOpt(current_value, str(current_value)))

        return opts

    # @st.cache_data
    def get_fk(_self, table_name: str, _updated: int):
        # TODO check, do we need caching, if so should be rewritten to match filter logic and reset cache after changing filter state
        fk_cols = [col for col in _self.cols if len(list(col.foreign_keys)) > 0]
        opts = {}
        
        for col in fk_cols:
            if not col.description:
                continue
                
            col_name = col.description
            
            if col_name in _self.foreign_key_options:
                opts[col_name] = _self.get_custom_foreign_opts(col_name, _self.foreign_key_options[col_name])
            else:
                opts[col_name] = _self.get_foreign_opts(col, next(iter(col.foreign_keys)))

        return opts
