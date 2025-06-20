from typing import Optional, Type
import streamlit as st
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql.filters import ExistingData
from streamlit_sql.input_fields import InputFields
from streamlit_sql.lib import get_pretty_name, log, set_state
from streamlit_sql.pydantic_utils import PydanticSQLAlchemyConverter, PydanticInputGenerator


class CreateRow:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        default_values: dict | None = None,
        base_key: str = "create",
        create_schema: Optional[Type[BaseModel]] = None,
        foreign_key_options: dict | None = None,
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.create_schema = create_schema
        self.foreign_key_options = foreign_key_options or {}

        self.default_values = default_values or {}
        self.base_key = base_key

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.existing_data = ExistingData(s, Model, self.default_values, foreign_key_options=self.foreign_key_options)
            self.input_fields = InputFields(
                Model, base_key, self.default_values, self.existing_data
            )
            
        # Initialize Pydantic input generator if schema provided
        if self.create_schema:
            self.pydantic_generator = PydanticInputGenerator(
                self.create_schema, base_key, self.foreign_key_options
            )
            # Pass connection for foreign key queries
            self.pydantic_generator.conn = self.conn
    
    def _preprocess_form_data(self, form_data: dict) -> dict:
        """Preprocess form data - simplified since str-based enums work naturally"""
        return form_data

    def _format_database_error(self, error: Exception) -> str:
        """Format database errors into user-friendly messages"""
        error_str = str(error)
        
        # Handle NULL identity key error (auto-generated primary keys)
        if "NULL identity key" in error_str:
            return ("⚠️ Database Configuration Issue: This table appears to use auto-generated IDs, "
                   "but the database is not properly configured for ID generation. "
                   "Please ensure your database table has auto-increment/sequence enabled for the ID column, "
                   "or exclude the ID field from your create schema.")
        
        # Handle unique constraint violations
        elif "UNIQUE constraint failed" in error_str or "duplicate key" in error_str.lower():
            return ("❌ Duplicate Entry: A record with these values already exists. "
                   "Please check for duplicate entries and try again.")
        
        # Handle foreign key constraint violations
        elif "FOREIGN KEY constraint failed" in error_str or "foreign key" in error_str.lower():
            return ("🔗 Invalid Reference: One or more referenced records don't exist. "
                   "Please ensure all referenced data is valid and try again.")
        
        # Handle NOT NULL constraint violations
        elif "NOT NULL constraint failed" in error_str or "cannot be null" in error_str.lower():
            return ("📝 Missing Required Fields: Some required fields are missing. "
                   "Please fill in all required fields and try again.")
        
        # Handle connection/timeout errors
        elif "connection" in error_str.lower() or "timeout" in error_str.lower():
            return ("🌐 Database Connection Issue: Unable to connect to the database. "
                   "Please check your connection and try again.")
        
        # Default fallback - return original error but more user-friendly
        else:
            return f"💾 Database Error: {error_str}"

    def get_fields(self):
        if self.create_schema:
            return self.get_pydantic_fields()
        else:
            return self.get_sqlalchemy_fields()
    
    def get_pydantic_fields(self):
        """Generate fields using Pydantic schema"""
        form_data = self.pydantic_generator.generate_form_data(self.default_values)
        return form_data
    
    def get_sqlalchemy_fields(self):
        """Original SQLAlchemy field generation logic"""
        cols = self.Model.__table__.columns
        created = {}
        for col in cols:
            col_name = col.description or col.name
            if col_name is None:
                continue
                
            default_value = self.default_values.get(col_name)

            if default_value:
                input_value = default_value
            else:
                input_value = self.input_fields.get_input_value(col, None)

            created[col_name] = input_value

        return created

    def show(self, pretty_name: str):
        st.subheader(pretty_name)

        with st.form(f"create_model_form_{pretty_name}_{self.base_key}", border=False):
            created = self.get_fields()
            create_btn = st.form_submit_button("Save", type="primary")

        if create_btn:
            if self.create_schema:
                return self.save_pydantic(created)
            else:
                return self.save_sqlalchemy(created)
        else:
            return None, None
    
    def save_pydantic(self, form_data: dict):
        """Save using Pydantic validation"""
        try:
            # Preprocess form data to handle enum conversions
            processed_data = self._preprocess_form_data(form_data)
            
            # Validate data using Pydantic schema
            validated_data = self.create_schema(**processed_data)
            
            # Convert to SQLAlchemy model
            row = PydanticSQLAlchemyConverter.pydantic_to_sqlalchemy(
                validated_data, self.Model
            )
            
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
                
        except ValidationError as e:
            error_msg = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            ss.stsql_updated += 1
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("CREATE", table_name, form_data, success=False)
            return False, f"Validation error: {error_msg}"
        except Exception as e:
            ss.stsql_updated += 1
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("CREATE", table_name, form_data, success=False)
            
            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = self._format_database_error(e)
            return False, error_msg
    
    def save_sqlalchemy(self, created: dict):
        """Original SQLAlchemy save logic"""
        try:
            row = self.Model(**created)
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
        except Exception as e:
            ss.stsql_updated += 1
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("CREATE", table_name, created, success=False)
            
            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = self._format_database_error(e)
            return False, error_msg

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Create {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()


class DeleteRows:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        rows_id: list[int],
        base_key: str
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.rows_id = rows_id
        self.base_key = f"{base_key}_stsql_delete_rows",

    @st.cache_data
    def get_rows_str(_self, rows_id: list[int]):
        id_col = _self.Model.__table__.columns.get("id")
        assert id_col is not None
        stmt = select(_self.Model).where(id_col.in_(rows_id))

        with _self.conn.session as s:
            rows = s.execute(stmt).scalars()
            rows_str = [str(row) for row in rows]

        return rows_str

    def show(self, pretty_name):
        st.subheader("Delete selected items?")

        rows_str = self.get_rows_str(self.rows_id)
        st.dataframe({pretty_name: rows_str}, hide_index=True)

        btn = st.button("Delete", key=self.base_key)
        if btn:
            id_col = self.Model.__table__.columns.get("id")
            assert id_col is not None
            lancs = []
            with self.conn.session as s:
                try:
                    for row_id in self.rows_id:
                        lanc = s.get(self.Model, row_id)
                        lancs.append(str(lanc))
                        s.delete(lanc)

                    s.commit()
                    ss.stsql_updated += 1
                    qtty = len(self.rows_id)
                    lancs_str = ", ".join(lancs)
                    table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                    log("DELETE", table_name, lancs_str)
                    return True, f"Successfully deleted {qtty}"
                except Exception as e:
                    ss.stsql_updated += 1
                    table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                    log("DELETE", table_name, "")
                    return False, str(e)
        else:
            return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Delete {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()
