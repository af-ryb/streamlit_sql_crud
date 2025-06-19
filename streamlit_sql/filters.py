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
    ) -> None:
        self.session = session
        self.Model = Model
        self.default_values = default_values
        self.row = row
        self.foreign_key_options = foreign_key_options or {}

        self.cols = Model.__table__.columns
        reg_values: Any = Model.registry._class_registry.values()
        self._models = [reg for reg in reg_values if hasattr(reg, "__tablename__")]

        table_name = Model.__tablename__
        self.text = self.get_text(table_name, ss.stsql_updated)
        self.dt = self.get_dt(table_name, ss.stsql_updated)
        self.fk = self.get_fk(table_name, ss.stsql_updated)

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
        query = fk_config['query']
        display_field = fk_config['display_field']
        value_field = fk_config['value_field']
        
        # Execute query to get rows
        rows = self.session.execute(query).scalars().all()
        
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
                # Check if current value already exists in opts
                if not any(opt.idx == current_value for opt in opts):
                    # Try to find the display value for current value by executing a targeted query
                    try:
                        # Get the model class from the query (assuming it's a simple select from a single table)
                        model_class = None
                        if hasattr(query, 'column_descriptions'):
                            model_class = query.column_descriptions[0]['type']
                        else:
                            # Try to extract from the query's froms
                            if query.froms:
                                model_class = query.froms[0].entity_namespace
                        
                        if model_class:
                            current_row_query = select(model_class).where(getattr(model_class, value_field) == current_value)
                            current_row = self.session.execute(current_row_query).scalars().first()
                            if current_row:
                                current_display = getattr(current_row, display_field)
                                opts.append(FkOpt(current_value, current_display))
                    except Exception:
                        # Fallback: just use the current value as display
                        opts.append(FkOpt(current_value, str(current_value)))
        
        return opts

    @st.cache_data
    def get_fk(_self, table_name: str, _updated: int):
        fk_cols = [col for col in _self.cols if len(list(col.foreign_keys)) > 0]
        opts = {}
        
        for col in fk_cols:
            if not col.description:
                continue
                
            col_name = col.description
            
            # Check if there's a custom foreign key option for this field
            if col_name in _self.foreign_key_options:
                opts[col_name] = _self.get_custom_foreign_opts(col_name, _self.foreign_key_options[col_name])
            else:
                # Use default foreign key handling
                opts[col_name] = _self.get_foreign_opts(col, next(iter(col.foreign_keys)))
                
        return opts
