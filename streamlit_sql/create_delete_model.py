from typing import Optional, Type
import streamlit as st
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

from streamlit_sql.filters import ExistingData
from streamlit_sql.input_fields import InputFields
from streamlit_sql.lib import get_pretty_name, log, set_state, format_database_error
from streamlit_sql.pydantic_utils import PydanticSQLAlchemyConverter
from streamlit_sql.pydantic_ui import PydanticCrudUi
from loguru import logger


class CreateRow:
    def __init__(self,
                 conn: SQLConnection,
                 model: type[DeclarativeBase],
                 default_values: dict | None = None,
                 key: str = "create",
                 create_schema: Optional[Type[BaseModel]] = None,
                 foreign_key_options: dict | None = None,
                 initial_data: dict | None = None,
                 ) -> None:
        self.conn = conn
        self.model = model
        self.create_schema = create_schema
        self.foreign_key_options = foreign_key_options or {}
        self.initial_data = initial_data or {}

        self.default_values = default_values or {}
        self.key_prefix = f"{key}_create"

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.existing_data = ExistingData(s, model, self.default_values, foreign_key_options=self.foreign_key_options)
            self.input_fields = InputFields(
                model, key_prefix=self.key_prefix, default_values=self.default_values, existing_data=self.existing_data
            )
            
        # Initialize PydanticUi if schema provided
        if self.create_schema:
            session_key = f"{self.key_prefix}_form_data"
            
            # Pre-populate form with initial_data if provided (for "copy" action)
            if self.initial_data:
                # Remove 'id' to avoid conflicts, as it's a new record
                self.initial_data.pop('id', None)
                set_state(session_key, self.initial_data)

            self.pydantic_ui = PydanticCrudUi(
                schema=self.create_schema, 
                key=self.key_prefix,
                session_state_key=session_key,
                foreign_key_options=self.foreign_key_options
            )
            
            # Load foreign key data for fields that need it
            self._load_foreign_key_data()


    def get_fields(self):
        if self.create_schema:
            return self.get_pydantic_fields()
        else:
            return self.get_sqlalchemy_fields()
    
    def get_pydantic_fields(self):
        """Generate fields using PydanticUi"""
        # Use PydanticUi to render the form with submit button
        form_data = self.pydantic_ui.render_with_submit("Save")
        return form_data
    
    def _load_foreign_key_data(self):
        """Load foreign key data from database for form fields."""
        for field_name, fk_config in self.foreign_key_options.items():
            try:
                query = fk_config['query']
                display_field = fk_config['display_field']
                value_field = fk_config['value_field']
                
                with self.conn.session as session:
                    rows = session.execute(query).scalars().all()
                    
                    # Convert to list of dicts for the input generator
                    options = []
                    for row in rows:
                        options.append({
                            value_field: getattr(row, value_field),
                            display_field: getattr(row, display_field)
                        })
                    
                    # Set the options in the input generator
                    self.pydantic_ui.input_generator.set_foreign_key_options(
                        field_name, options, display_field, value_field
                    )
                    
            except Exception as e:
                # Log error but continue - field will fall back to text input
                logger.warning(f"Failed to load foreign key data for {field_name}: {e}")
    
    def get_sqlalchemy_fields(self):
        """Original SQLAlchemy field generation logic"""
        cols = self.model.__table__.columns
        created = {}
        for col in cols:
            col_name = col.description or col.name
            if col_name is None:
                continue
                
            default_value = self.default_values.get(col_name)
            initial_value = self.initial_data.get(col_name)

            if default_value:
                input_value = default_value
            else:
                input_value = self.input_fields.get_input_value(col, initial_value)

            created[col_name] = input_value

        return created

    def show(self, pretty_name: str):
        st.subheader(pretty_name)

        if self.create_schema:
            # Use PydanticUi which handles forms internally
            created = self.get_pydantic_fields()
            if created:
                return self.save_pydantic(created)
            else:
                return None, None
        else:
            # Use traditional form for SQLAlchemy-only mode
            with st.form(f"create_model_form_{pretty_name}_{self.key_prefix}", border=False):
                created = self.get_sqlalchemy_fields()
                create_btn = st.form_submit_button("Save", type="primary")

            if create_btn:
                return self.save_sqlalchemy(created)
            else:
                return None, None
    
    def save_pydantic(self, validated_data: BaseModel):
        """Save using pre-validated Pydantic data from PydanticUi"""
        try:
            # Convert to SQLAlchemy model
            row = PydanticSQLAlchemyConverter.pydantic_to_sqlalchemy(
                validated_data, self.model
            )
            
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = getattr(self.model, '__tablename__', self.model.__name__)
                log("CREATE", table_name, row)
                
                # Clear the form data after successful save
                session_key = f"{self.key_prefix}_form_data"
                if session_key in st.session_state:
                    del st.session_state[session_key]
                    
                return True, f"Created successfully {row}"
                
        except Exception as e:
            ss.stsql_updated += 1
            table_name = getattr(self.model, '__tablename__', self.model.__name__)
            log("CREATE", table_name, validated_data.model_dump(), success=False)
            
            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg

    def save_sqlalchemy(self, created: dict):
        """Original SQLAlchemy save logic"""
        try:
            row = self.model(**created)
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = getattr(self.model, '__tablename__', self.model.__name__)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
        except Exception as e:
            ss.stsql_updated += 1
            table_name = getattr(self.model, '__tablename__', self.model.__name__)
            log("CREATE", table_name, created, success=False)
            
            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg

    def show_dialog(self):
        pretty_name = get_pretty_name(self.model.__tablename__)

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
    def __init__(self,
                 conn: SQLConnection,
                 model: type[DeclarativeBase],
                 rows_id: list[int],
                 key: str
                 ) -> None:
        self.conn = conn
        self.model = model
        self.rows_id = rows_id
        self.key_prefix = f"{key}_delete"

    @st.cache_data
    def get_rows_str(_self, rows_id: list[int]):
        id_col = _self.model.__table__.columns.get("id")
        assert id_col is not None
        stmt = select(_self.model).where(id_col.in_(rows_id))

        with _self.conn.session as s:
            rows = s.execute(stmt).scalars()
            rows_str = [str(row) for row in rows]

        return rows_str

    def show(self, pretty_name):
        st.subheader("Delete selected items?")

        rows_str = self.get_rows_str(self.rows_id)
        st.dataframe({pretty_name: rows_str}, hide_index=True)

        btn = st.button("Delete", key=f"{self.key_prefix}_del_btn")
        if btn:
            id_col = self.model.__table__.columns.get("id")
            assert id_col is not None
            lancs = []
            with self.conn.session as s:
                try:
                    for row_id in self.rows_id:
                        lanc = s.get(self.model, row_id)
                        lancs.append(str(lanc))
                        s.delete(lanc)

                    s.commit()
                    ss.stsql_updated += 1
                    qtty = len(self.rows_id)
                    lancs_str = ", ".join(lancs)
                    table_name = getattr(self.model, '__tablename__', self.model.__name__)
                    log("DELETE", table_name, lancs_str)
                    return True, f"Successfully deleted {qtty}"
                except Exception as e:
                    ss.stsql_updated += 1
                    table_name = getattr(self.model, '__tablename__', self.model.__name__)
                    log("DELETE", table_name, "")
                    return False, format_database_error(e)
        else:
            return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.model.__tablename__)

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
