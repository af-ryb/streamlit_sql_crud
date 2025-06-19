import streamlit as st
from typing import Optional, Type, Union
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator

from streamlit_sql import many
from streamlit_sql.filters import ExistingData
from streamlit_sql.input_fields import InputFields
from streamlit_sql.lib import get_pretty_name, log, set_state
from streamlit_sql.pydantic_utils import PydanticInputGenerator


class UpdateRow:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        row_id: int | str,
        default_values: dict | None = None,
        update_show_many: bool = False,
        update_schema: Optional[Type[BaseModel]] = None,
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.row_id = row_id
        self.default_values = default_values or {}
        self.update_show_many = update_show_many
        self.update_schema = update_schema

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.row = s.get_one(Model, row_id)
            self.existing_data = ExistingData(s, Model, self.default_values, self.row)

        self.input_fields = InputFields(
            Model, "update", self.default_values, self.existing_data
        )
        
        # Initialize Pydantic input generator if schema provided
        if self.update_schema:
            # Get current row values for pre-populating form
            self.current_values = {}
            for col in self.Model.__table__.columns:
                col_name = col.description or col.name
                if col_name and hasattr(self.row, col_name):
                    self.current_values[col_name] = getattr(self.row, col_name)
            
            self.pydantic_generator = PydanticInputGenerator(
                self.update_schema, "update"
            )
    
    def _preprocess_form_data(self, form_data: dict) -> dict:
        """Preprocess form data - simplified since str-based enums work naturally"""
        return form_data

    def get_updates(self):
        if self.update_schema:
            return self.get_pydantic_updates()
        else:
            return self.get_sqlalchemy_updates()
    
    def get_pydantic_updates(self):
        """Generate updates using Pydantic schema"""
        form_data = self.pydantic_generator.generate_form_data(self.current_values)
        return form_data
    
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

    def save(self, updated: dict):
        if self.update_schema:
            return self.save_pydantic(updated)
        else:
            return self.save_sqlalchemy(updated)
    
    def save_pydantic(self, form_data: dict):
        """Save using Pydantic validation"""
        try:
            # Preprocess form data to handle enum conversions
            processed_data = self._preprocess_form_data(form_data)
            
            # Validate data using Pydantic schema
            validated_data = self.update_schema(**processed_data)
            
            with self.conn.session as s:
                stmt = select(self.Model).where(
                    self.Model.__table__.columns.id == validated_data.id
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
                return True, f"Updated successfully {row}"
                
        except ValidationError as e:
            error_msg = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("UPDATE", table_name, form_data, success=False)
            return False, f"Validation error: {error_msg}"
        except Exception as e:
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("UPDATE", table_name, form_data, success=False)
            return False, str(e)
    
    def save_sqlalchemy(self, updated: dict):
        """Original SQLAlchemy save logic"""
        with self.conn.session as s:
            try:
                stmt = select(self.Model).where(
                    self.Model.__table__.columns.id == updated["id"]
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
                return False, str(e)

    def show(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)
        st.subheader(pretty_name)
        with st.form(f"update_model_form_{pretty_name}", border=False):
            updated = self.get_updates()
            update_btn = st.form_submit_button("Save")

        if self.update_show_many:
            many.show_rels(self.conn, self.Model, self.row_id)

        if update_btn:
            ss.stsql_updated += 1
            return self.save(updated)
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
