
import streamlit as st
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator
from typing import Optional, Type, Union
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

from streamlit_pydantic_crud import many
from streamlit_pydantic_crud.filters import ExistingData
from streamlit_pydantic_crud.input_fields import InputFields
from streamlit_pydantic_crud.lib import get_pretty_name, log, set_state, format_database_error
from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi
from streamlit_pydantic_crud.utils import convert_numpy_to_python
from loguru import logger


class UpdateRow:
    def __init__(self,
                 conn: SQLConnection,
                 model: type[DeclarativeBase],
                 row_id: int | str,
                 default_values: dict | None = None,
                 update_show_many: bool = False,
                 update_schema: Optional[Type[BaseModel]] = None,
                 foreign_key_options: dict | None = None,
                 many_to_many_fields: dict | None = None,
                 key: str = "update",
                 dt_filters: dict | None = None,
                 no_dt_filters: dict | None = None,
                 ) -> None:
        self.conn = conn
        self.model = model
        self.row_id = row_id
        self.default_values = default_values or {}
        self.update_show_many = update_show_many
        self.update_schema = update_schema
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        self.key_prefix = f"{key}_update"
        self.dt_filters = dt_filters or {}
        self.no_dt_filters = no_dt_filters or {}

        set_state("stsql_updated", 0)

        with conn.session as s:
            # Load row with many-to-many relationships if needed
            if self.many_to_many_fields:
                from sqlalchemy.orm import selectinload
                
                # Build options for eager loading
                options = []
                for field_name, config in self.many_to_many_fields.items():
                    relationship_attr = getattr(self.model, config['relationship'])
                    options.append(selectinload(relationship_attr))
                
                # Use query with selectinload to get the row with relationships
                self.row = s.query(self.model).options(*options).filter(
                    self.model.id == row_id
                ).one()
            else:
                self.row = s.get_one(model, row_id)
                
            self.existing_data = ExistingData(s, model,
                                              default_values=self.default_values, row=self.row,
                                              foreign_key_options=self.foreign_key_options,
                                              dt_filters=self.dt_filters,
                                              no_dt_filters=self.no_dt_filters)

        self.input_fields = InputFields(
            model, key_prefix=self.key_prefix, default_values=self.default_values, existing_data=self.existing_data
        )
        
        # Initialize PydanticUi if schema provided
        if self.update_schema:
            # Get current row values for pre-populating form
            self.current_values = {}
            for col in self.model.__table__.columns:
                col_name = col.description or col.name
                if col_name and hasattr(self.row, col_name):
                    value = getattr(self.row, col_name)
                    # Convert certain types for proper display
                    if value is not None:
                        value = convert_numpy_to_python(value, self.model)
                    self.current_values[col_name] = value
            
            # Add many-to-many field values 
            for field_name, config in self.many_to_many_fields.items():
                relationship_name = config['relationship']
                if hasattr(self.row, relationship_name):
                    # Get currently selected objects
                    current_objects = getattr(self.row, relationship_name)
                    # Convert to list of IDs for multiselect
                    self.current_values[field_name] = [obj.id for obj in current_objects]
                else:
                    logger.warning(f"Row does not have relationship {relationship_name}")
            
            # populate session state with current values
            # Clear existing data before setting new values to avoid stale data
            if self.get_session_key in st.session_state:
                del st.session_state[self.get_session_key]
            set_state(self.get_session_key, self.current_values)
            
            self.pydantic_ui = PydanticCrudUi(
                schema=self.update_schema, 
                key=self.key_prefix,
                session_state_key=self.get_session_key,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
            )
            
            # Set operation type to 'update' for proper null value handling
            self.pydantic_ui.set_operation_type('update')
            
            # Load foreign key data for fields that need it
            self._load_foreign_key_data()
            self._load_many_to_many_data()

    @property
    def get_session_key(self):
        return f"{self.key_prefix}_form_data"


    def get_updates(self):
        if self.update_schema:
            return self.get_pydantic_updates()
        else:
            return self.get_sqlalchemy_updates()
    
    def get_pydantic_updates(self):
        """Generate updates using PydanticUi"""
        # Use PydanticUi to render the form with submit button
        form_data, submitted = self.pydantic_ui.render_with_submit("Save")
        return form_data if submitted else None
    
    def _load_many_to_many_data(self):
        """Load many-to-many relationship data from the database."""
        for field_name, m2m_config in self.many_to_many_fields.items():
            try:
                relationship_name = m2m_config['relationship']
                display_field = m2m_config['display_field']
                
                # Get the related model from the relationship
                related_model = getattr(self.model, relationship_name).property.mapper.class_
                
                # Base query for the related model
                query = select(related_model)
                
                # Apply optional filter
                if 'filter' in m2m_config:
                    query = m2m_config['filter'](query)

                with self.conn.session as session:
                    rows = session.execute(query).scalars().all()

                    # Set options in PydanticUi's input generator
                    self.pydantic_ui.input_generator.set_many_to_many_options(
                        field_name, rows, display_field
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to load many-to-many data for {field_name}: {e}")

    def _load_foreign_key_data(self):
        """Load foreign key data from database for form fields using filtered options."""
        for field_name, fk_config in self.foreign_key_options.items():
            try:
                display_field = fk_config['display_field']
                value_field = fk_config['value_field']
                
                # Use filtered foreign key options from ExistingData instead of raw query
                if hasattr(self.existing_data, 'fk') and field_name in self.existing_data.fk:
                    fk_opts = self.existing_data.fk[field_name]
                    
                    # Convert FkOpt objects to list of dicts for the input generator
                    options = []
                    for fk_opt in fk_opts:
                        options.append({
                            value_field: fk_opt.idx,
                            display_field: fk_opt.name
                        })
                    
                else:
                    # Fallback to original logic if filtered options not available
                    query = fk_config['query']
                    
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
        cols = self.model.__table__.columns
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
                id_col = self.model.__table__.columns.get('id')
                stmt = select(self.model).where(
                    id_col == validated_data.id
                )
                row = s.execute(stmt).scalar_one()
                
                # Separate many-to-many fields from the main data
                m2m_data = {}
                main_data = validated_data.model_dump(exclude_unset=True)
                
                for field_name in self.many_to_many_fields.keys():
                    if field_name in main_data:
                        m2m_data[field_name] = main_data.pop(field_name)

                # Update only the fields present in the validated data
                for field_name, field_value in main_data.items():
                    if hasattr(row, field_name):
                        setattr(row, field_name, field_value)

                # Handle many-to-many relationships
                for field_name, selected_options in m2m_data.items():
                    relationship_name = self.many_to_many_fields[field_name]['relationship']
                    related_model = getattr(self.model, relationship_name).property.mapper.class_
                    
                    # Get the related objects from the database
                    related_objects = s.query(related_model).filter(related_model.id.in_(selected_options)).all()
                    
                    # Update the relationship
                    getattr(row, relationship_name)[:] = related_objects

                s.add(row)
                s.commit()
                table_name = getattr(self.model, '__tablename__', self.model.__name__)
                log("UPDATE", table_name, row)
                
                # Clear the form data after successful save
                if self.get_session_key in st.session_state:
                    del st.session_state[self.get_session_key]
                    
                return True, f"Updated successfully {row}"
                
        except Exception as e:
            table_name = getattr(self.model, '__tablename__', self.model.__name__)
            log("UPDATE", table_name, validated_data.model_dump(), success=False)
            
            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg
    
    
    def save_sqlalchemy(self, updated: dict):
        """Original SQLAlchemy save logic"""
        with self.conn.session as s:
            try:
                id_col = self.model.__table__.columns.get('id')
                stmt = select(self.model).where(
                    id_col == updated["id"]
                )
                row = s.execute(stmt).scalar_one()
                for k, v in updated.items():
                    setattr(row, k, v)

                s.add(row)
                s.commit()
                table_name = getattr(self.model, '__tablename__', self.model.__name__)
                log("UPDATE", table_name, row)
                return True, f"Updated successfully {row}"
            except Exception as e:
                updated_list = [f"{k}: {v}" for k, v in updated.items()]
                updated_str = ", ".join(updated_list)
                table_name = getattr(self.model, '__tablename__', self.model.__name__)
                log("UPDATE", table_name, updated_str, success=False)
                
                # Handle specific SQLAlchemy errors with user-friendly messages
                error_msg = format_database_error(e)
                return False, error_msg

    def show(self):
        pretty_name = get_pretty_name(self.model.__tablename__)
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
            many.show_rels(self.conn, self.model, self.row_id)
        
        return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.model.__tablename__)

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
    disabled_add = qtty_selected > 1
    disabled_edit = qtty_selected != 1
    disabled_delete = qtty_selected == 0

    if qtty_selected == 1:
        add_icon = ":material/content_copy:"
        add_help = "Copy"
    else:
        add_icon = ":material/add:"
        add_help = "Add"

    with container:
        add_col, edit_col, del_col, _empty_col = st.columns([1, 1, 1, 6])

        add_btn = add_col.button(
            "",
            help=add_help,
            icon=add_icon,
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
            if qtty_selected == 1:
                return "copy"
            return "add"
        if edit_btn:
            return "edit"
        if del_btn:
            return "delete"

        return None
