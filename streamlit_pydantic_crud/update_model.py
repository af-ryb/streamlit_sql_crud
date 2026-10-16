import streamlit as st
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, selectinload
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud import many
from streamlit_pydantic_crud.filters import ExistingData
from streamlit_pydantic_crud.form_options import load_form_options
from streamlit_pydantic_crud.input_fields import InputFields
from streamlit_pydantic_crud.lib import (
    format_database_error,
    get_pretty_name,
    log,
    set_state,
    show_crud_dialog,
)
from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi
from streamlit_pydantic_crud.utils import (
    convert_numpy_to_python,
    pk_attr,
    pk_column,
    pk_name,
    tablename,
)


class UpdateRow:
    """Edit dialog for one row.

    ``dt_filters`` / ``no_dt_filters`` are accepted for compatibility but not
    applied: editing lists all foreign-key options, unlike creating.
    """

    def __init__(
        self,
        conn: SQLConnection,
        model: type[DeclarativeBase],
        row_id: int | str,
        default_values: dict | None = None,
        update_show_many: bool = False,
        update_schema: type[BaseModel] | None = None,
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
        self.key = key
        self.key_prefix = f"{key}_update"
        self.dt_filters = dt_filters or {}
        self.no_dt_filters = no_dt_filters or {}

        set_state("stsql_updated", 0)

        with conn.session as s:
            # Load row with many-to-many relationships if needed
            if self.many_to_many_fields:
                # Build options for eager loading
                options = []
                for config in self.many_to_many_fields.values():
                    relationship_attr = getattr(self.model, config["relationship"])
                    options.append(selectinload(relationship_attr))

                # Use query with selectinload to get the row with relationships
                self.row = (
                    s.query(self.model)
                    .options(*options)
                    .filter(pk_attr(self.model) == row_id)
                    .one()
                )
            else:
                self.row = s.get_one(model, row_id)

            if not self.update_schema:
                """SQLAlchemy-mode inputs; Pydantic forms never read them."""
                self.existing_data = ExistingData(
                    s,
                    model,
                    default_values=self.default_values,
                    row=self.row,
                    foreign_key_options=self.foreign_key_options,
                )
                self.input_fields = InputFields(
                    model,
                    key_prefix=self.key_prefix,
                    default_values=self.default_values,
                    existing_data=self.existing_data,
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
                relationship_name = config["relationship"]
                if hasattr(self.row, relationship_name):
                    # Get currently selected objects
                    current_objects = getattr(self.row, relationship_name)
                    related_model = getattr(
                        self.model, relationship_name
                    ).property.mapper.class_
                    related_pk = pk_name(related_model)
                    # Convert to list of PKs for multiselect
                    self.current_values[field_name] = [
                        getattr(obj, related_pk) for obj in current_objects
                    ]
                else:
                    logger.warning(
                        f"Row does not have relationship {relationship_name}"
                    )

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
                pk_name=pk_name(self.model),
            )

            # Set operation type to 'update' for proper null value handling
            self.pydantic_ui.set_operation_type("update")

            load_form_options(
                self.pydantic_ui,
                conn,
                model,
                self.foreign_key_options,
                self.many_to_many_fields,
                row=self.row,
            )

    @property
    def get_session_key(self):
        return f"{self.key_prefix}_form_data"

    def get_pydantic_updates(self):
        """Generate updates using PydanticUi"""
        # Use PydanticUi to render the form with submit button
        form_data, submitted = self.pydantic_ui.render_with_submit("Save")
        return form_data if submitted else None

    def get_sqlalchemy_updates(self):
        """Original SQLAlchemy update logic"""
        cols = self.model.__table__.columns
        updated = {}

        for col in cols:
            col_name = col.description or col.name
            if col_name is None:
                continue

            col_value = getattr(self.row, col_name)

            if col_name in self.default_values:
                input_value = col_value
            else:
                input_value = self.input_fields.get_input_value(col, col_value)

            updated[col_name] = input_value

        return updated

    def save_pydantic(self, validated_data: BaseModel):
        """Save using pre-validated Pydantic data from PydanticUi"""
        try:
            with self.conn.session as s:
                id_col = pk_column(self.model)
                stmt = select(self.model).where(
                    id_col == getattr(validated_data, pk_name(self.model))
                )
                row = s.execute(stmt).scalar_one()

                # Separate many-to-many fields from the main data
                m2m_data = {}
                main_data = validated_data.model_dump(exclude_unset=True)

                for field_name in self.many_to_many_fields:
                    if field_name in main_data:
                        m2m_data[field_name] = main_data.pop(field_name)

                # Update only the fields present in the validated data
                for field_name, field_value in main_data.items():
                    if hasattr(row, field_name):
                        setattr(row, field_name, field_value)

                # Handle many-to-many relationships
                for field_name, selected_options in m2m_data.items():
                    relationship_name = self.many_to_many_fields[field_name][
                        "relationship"
                    ]
                    related_model = getattr(
                        self.model, relationship_name
                    ).property.mapper.class_

                    # Get the related objects from the database
                    related_objects = (
                        s.query(related_model)
                        .filter(pk_attr(related_model).in_(selected_options))
                        .all()
                    )

                    # Update the relationship
                    getattr(row, relationship_name)[:] = related_objects

                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = tablename(self.model)
                log("UPDATE", table_name, row)

                # Clear the form data after successful save
                if self.get_session_key in st.session_state:
                    del st.session_state[self.get_session_key]

                return True, f"Updated successfully {row}"

        except Exception as e:
            ss.stsql_updated += 1
            table_name = tablename(self.model)
            log("UPDATE", table_name, validated_data.model_dump(), success=False)
            logger.exception(f"Update failed for {table_name}")

            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg

    def save_sqlalchemy(self, updated: dict):
        """Original SQLAlchemy save logic"""
        with self.conn.session as s:
            try:
                id_col = pk_column(self.model)
                stmt = select(self.model).where(id_col == updated[pk_name(self.model)])
                row = s.execute(stmt).scalar_one()
                for k, v in updated.items():
                    setattr(row, k, v)

                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = tablename(self.model)
                log("UPDATE", table_name, row)
                return True, f"Updated successfully {row}"
            except Exception as e:
                ss.stsql_updated += 1
                updated_list = [f"{k}: {v}" for k, v in updated.items()]
                updated_str = ", ".join(updated_list)
                table_name = tablename(self.model)
                log("UPDATE", table_name, updated_str, success=False)
                logger.exception(f"Update failed for {table_name}")

                # Handle specific SQLAlchemy errors with user-friendly messages
                error_msg = format_database_error(e)
                return False, error_msg

    def show(self):
        pretty_name = get_pretty_name(tablename(self.model))
        st.subheader(pretty_name)

        if self.update_schema:
            # Use PydanticUi which handles forms internally
            updated = self.get_pydantic_updates()
            if updated:
                return self.save_pydantic(updated)
        else:
            # Use traditional form for SQLAlchemy-only mode
            form_key = f"update_model_form_{pretty_name}_{self.key_prefix}"
            with st.form(form_key, border=False):
                updated = self.get_sqlalchemy_updates()
                update_btn = st.form_submit_button("Save")

            if update_btn:
                return self.save_sqlalchemy(updated)

        if self.update_show_many:
            many.show_rels(self.conn, self.model, self.row_id)

        return None, None

    def show_dialog(self) -> None:
        """Open the edit dialog."""
        pretty_name = get_pretty_name(tablename(self.model))
        show_crud_dialog(f"Edit {pretty_name}", self.key, self.show)


def action_btns(
    container: DeltaGenerator,
    qtty_selected: int,
    opened: bool,
    show_create_btn: bool,
    show_delete_btn: bool,
    key: str,
):
    disabled_add = (qtty_selected > 1) or not show_create_btn
    disabled_edit = qtty_selected != 1
    disabled_delete = (qtty_selected == 0) or not show_delete_btn

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
            width="stretch",
            key=f"{key}_stsql_action_add",
        )

        edit_btn = edit_col.button(
            "",
            help="Edit",
            icon=":material/edit:",
            type="secondary",
            disabled=disabled_edit,
            width="stretch",
            key=f"{key}_stsql_action_edit",
        )

        del_btn = del_col.button(
            "",
            help="Delete",
            icon=":material/delete:",
            type="primary",
            disabled=disabled_delete,
            width="stretch",
            key=f"{key}_stsql_action_delete",
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
