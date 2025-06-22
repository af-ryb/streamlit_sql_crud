import streamlit as st
from typing import Optional, Type, Union
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator

from streamlit_sql import many
from streamlit_sql.filters import ExistingData
from streamlit_sql.input_fields import InputFields
from streamlit_sql.lib import get_pretty_name, log, set_state
from streamlit_sql.pydantic_ui import PydanticUi
from loguru import logger


class UpdateRow:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        row_id: int | str,
        default_values: dict | None = None,
        update_show_many: bool = False,
        update_schema: Optional[Type[BaseModel]] = None,
        foreign_key_options: dict | None = None,
        key: str = "update",
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.row_id = row_id
        self.default_values = default_values or {}
        self.update_show_many = update_show_many
        self.update_schema = update_schema
        self.foreign_key_options = foreign_key_options or {}
        self.key_prefix = f"{key}_update"

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.row = s.get_one(Model, row_id)
            self.existing_data = ExistingData(s, Model,
                                              default_values=self.default_values, row=self.row,
                                              foreign_key_options=self.foreign_key_options)

        self.input_fields = InputFields(
            Model, key_prefix=self.key_prefix, default_values=self.default_values, existing_data=self.existing_data
        )
        
        # Initialize PydanticUi if schema provided
        if self.update_schema:
            # Get current row values for pre-populating form
            self.current_values = {}
            for col in self.Model.__table__.columns:
                col_name = col.description or col.name
                if col_name and hasattr(self.row, col_name):
                    value = getattr(self.row, col_name)
                    # Convert certain types for proper display
                    if value is not None:
                        from streamlit_sql.utils import convert_numpy_to_python
                        value = convert_numpy_to_python(value, self.Model)
                    self.current_values[col_name] = value
            
            # Create session state key and pre-populate with current values
            session_key = f"{self.key_prefix}_form_data"
            import streamlit as st
            st.session_state[session_key] = self.current_values
            
            self.pydantic_ui = PydanticUi(
                schema=self.update_schema, 
                key=self.key_prefix,
                session_state_key=session_key,
                foreign_key_options=self.foreign_key_options
            )
            
            # Load foreign key data for fields that need it
            self._load_foreign_key_data()
    
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
                   "Please ensure your database table has auto-increment/sequence enabled for the ID column.")
        
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

    def get_updates(self):
        if self.update_schema:
            return self.get_pydantic_updates()
        else:
            return self.get_sqlalchemy_updates()
    
    def get_pydantic_updates(self):
        """Generate updates using PydanticUi"""
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
    
    def get_sqlalchemy_updates(self):
        """Original SQLAlchemy update logic"""
        cols = self.Model.__table__.columns
        updated = {}

        for col in cols:
            col_name = col.description or col.name
            if col_name is None:
                continue
                
            col_value = getattr(self.row, col_name)
            default_value = self.default_values.get(col_name)

            if default_value:
                input_value = col_value
            else:
                input_value = self.input_fields.get_input_value(col, col_value)

            updated[col_name] = input_value

        return updated

    def save(self, updated: Union[dict, BaseModel]):
        if self.update_schema and isinstance(updated, BaseModel):
            return self.save_pydantic(updated)
        elif isinstance(updated, dict):
            return self.save_sqlalchemy(updated)
        else:
            raise ValueError(f"Invalid updated data type: {type(updated)}")
    
    def save_pydantic(self, validated_data: BaseModel):
        """Save using pre-validated Pydantic data from PydanticUi"""
        try:
            with self.conn.session as s:
                id_col = self.Model.__table__.columns.get('id')
                stmt = select(self.Model).where(
                    id_col == validated_data.id
                )
                row = s.execute(stmt).scalar_one()
                
                # Update only the fields present in the validated data
                for field_name, field_value in validated_data.model_dump(exclude_unset=True).items():
                    if hasattr(row, field_name):
                        setattr(row, field_name, field_value)

                s.add(row)
                s.commit()
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("UPDATE", table_name, row)
                
                # Clear the form data after successful save
                session_key = f"{self.key_prefix}_form_data"
                if session_key in st.session_state:
                    del st.session_state[session_key]
                    
                return True, f"Updated successfully {row}"
                
        except Exception as e:
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("UPDATE", table_name, validated_data.model_dump(), success=False)
            
            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = self._format_database_error(e)
            return False, error_msg
    
    
    def save_sqlalchemy(self, updated: dict):
        """Original SQLAlchemy save logic"""
        with self.conn.session as s:
            try:
                id_col = self.Model.__table__.columns.get('id')
                stmt = select(self.Model).where(
                    id_col == updated["id"]
                )
                row = s.execute(stmt).scalar_one()
                for k, v in updated.items():
                    setattr(row, k, v)

                s.add(row)
                s.commit()
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("UPDATE", table_name, row)
                return True, f"Updated successfully {row}"
            except Exception as e:
                updated_list = [f"{k}: {v}" for k, v in updated.items()]
                updated_str = ", ".join(updated_list)
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("UPDATE", table_name, updated_str, success=False)
                
                # Handle specific SQLAlchemy errors with user-friendly messages
                error_msg = self._format_database_error(e)
                return False, error_msg

    def show(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)
        st.subheader(pretty_name)
        
        if self.update_schema:
            # Use PydanticUi which handles forms internally
            updated = self.get_pydantic_updates()
            if updated:
                ss.stsql_updated += 1
                return self.save_pydantic(updated)
        else:
            # Use traditional form for SQLAlchemy-only mode
            with st.form(f"update_model_form_{pretty_name}", border=False):
                updated = self.get_sqlalchemy_updates()
                update_btn = st.form_submit_button("Save")

            if update_btn:
                ss.stsql_updated += 1
                return self.save_sqlalchemy(updated)
        
        if self.update_show_many:
            many.show_rels(self.conn, self.Model, self.row_id)
        
        return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Edit {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show()

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()


def action_btns(container: DeltaGenerator, qtty_selected: int, opened: bool, key: str):
    set_state("stsql_action", "")
    disabled_add = qtty_selected > 0
    disabled_edit = qtty_selected != 1
    disabled_delete = qtty_selected == 0

    with container:
        add_col, edit_col, del_col, _empty_col = st.columns([1, 1, 1, 6])

        add_btn = add_col.button(
            "",
            help="Add",
            icon=":material/add:",
            type="secondary",
            disabled=disabled_add,
            use_container_width=True,
            key=f'{key}_stsql_action_add',
        )

        edit_btn = edit_col.button(
            "",
            help="Edit",
            icon=":material/edit:",
            type="secondary",
            disabled=disabled_edit,
            use_container_width=True,
            key=f'{key}_stsql_action_edit',
        )

        del_btn = del_col.button(
            "",
            help="Delete",
            icon=":material/delete:",
            type="primary",
            disabled=disabled_delete,
            use_container_width=True,
            key=f'{key}_stsql_action_delete',
        )

        if opened:
            return None
        if add_btn:
            return "add"
        if edit_btn:
            return "edit"
        if del_btn:
            return "delete"

        return None
