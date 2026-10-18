"""The edit dialog: a form seeded from one database row, plus 1:N panels."""

from typing import Any

import streamlit as st
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.config_types import (
    ForeignKeyOptions,
    ManyToManyFields,
    MappedModel,
)
from streamlit_pydantic_crud.dialogs import one_to_many
from streamlit_pydantic_crud.dialogs.frame import show_crud_dialog
from streamlit_pydantic_crud.dialogs.persist import (
    form_data_key,
    handle_save_error,
    handle_save_ok,
    json_none_as_sql_null,
    load_related,
    m2m_load_options,
    pop_m2m_data,
)
from streamlit_pydantic_crud.forms.options import ExistingData, load_form_options
from streamlit_pydantic_crud.forms.sa_fields import NO_INPUT, InputFields
from streamlit_pydantic_crud.helpers.display import get_pretty_name
from streamlit_pydantic_crud.helpers.sa_model import (
    column_label,
    declarative_model,
    pk_attr,
    pk_column,
    pk_name,
    related_model,
    tablename,
)
from streamlit_pydantic_crud.helpers.values import (
    convert_numpy_to_python,
    numpy_scalar_to_python,
)
from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi


class UpdateRow:
    """Edit dialog for one row.

    Page filters do not apply: editing lists all foreign-key options, unlike
    creating.
    """

    def __init__(
        self,
        conn: SQLConnection,
        model: type[MappedModel],
        row_id: int | str,
        default_values: dict | None = None,
        update_show_many: bool = False,
        update_schema: type[BaseModel] | None = None,
        foreign_key_options: ForeignKeyOptions | None = None,
        many_to_many_fields: ManyToManyFields | None = None,
        key: str = "update",
    ) -> None:
        self.conn = conn
        self.model = declarative_model(model)
        self.row_id = row_id
        self.default_values = default_values or {}
        self.update_show_many = update_show_many
        self.update_schema = update_schema
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        self.key = key
        self.key_prefix = f"{key}_update"

        with conn.session as s:
            if self.many_to_many_fields:
                """Load the row with its many-to-many relationships."""
                options = m2m_load_options(self.model, self.many_to_many_fields)
                self.row = (
                    s.query(self.model)
                    .options(*options)
                    .filter(pk_attr(self.model) == row_id)
                    .one()
                )
            else:
                self.row = s.get_one(self.model, row_id)

            if not self.update_schema:
                """SQLAlchemy-mode inputs; Pydantic forms never read them."""
                self.existing_data = ExistingData(
                    s,
                    self.model,
                    default_values=self.default_values,
                    row=self.row,
                    foreign_key_options=self.foreign_key_options,
                )
                self.input_fields = InputFields(
                    self.model,
                    key_prefix=self.key_prefix,
                    default_values=self.default_values,
                    existing_data=self.existing_data,
                )

        if self.update_schema:
            """Prefill the Pydantic form from the row's current values."""
            self.current_values = {}
            for col in self.model.__table__.columns:
                col_name = column_label(col)
                if hasattr(self.row, col_name):
                    value = getattr(self.row, col_name)
                    if col.primary_key:
                        value = convert_numpy_to_python(value, self.model)
                    else:
                        value = numpy_scalar_to_python(value)
                    self.current_values[col_name] = value

            for field_name, config in self.many_to_many_fields.items():
                relationship_name = config["relationship"]
                if hasattr(self.row, relationship_name):
                    current_objects = getattr(self.row, relationship_name)
                    related = related_model(self.model, relationship_name)
                    related_pk = pk_name(related)
                    """The multiselect holds the PKs of the selected rows."""
                    self.current_values[field_name] = [
                        getattr(obj, related_pk) for obj in current_objects
                    ]
                else:
                    logger.warning(
                        f"Row does not have relationship {relationship_name}"
                    )

            st.session_state[self.get_session_key] = self.current_values

            self.pydantic_ui = PydanticCrudUi(
                schema=self.update_schema,
                key=self.key_prefix,
                session_state_key=self.get_session_key,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
                pk_name=pk_name(self.model),
            )

            self.pydantic_ui.set_operation_type("update")

            load_form_options(
                self.pydantic_ui,
                conn,
                self.model,
                self.foreign_key_options,
                self.many_to_many_fields,
                row=self.row,
            )

    @property
    def get_session_key(self) -> str:
        return form_data_key(self.key_prefix)

    def get_pydantic_updates(self) -> BaseModel | None:
        """Render the Pydantic form; return its data once submitted."""
        form_data, submitted = self.pydantic_ui.render_with_submit("Save")
        return form_data if submitted else None

    def get_sqlalchemy_updates(self) -> dict[str, Any]:
        """Original SQLAlchemy update logic"""
        cols = self.model.__table__.columns
        updated = {}

        for col in cols:
            col_name = column_label(col)
            col_value = getattr(self.row, col_name)

            if col_name in self.default_values:
                input_value = col_value
            else:
                input_value = self.input_fields.get_input_value(col, col_value)

            if input_value is not NO_INPUT:
                updated[col_name] = input_value

        return updated

    def save_pydantic(self, validated_data: BaseModel) -> tuple[bool, str]:
        """Save using pre-validated Pydantic data from PydanticUi"""
        try:
            with self.conn.session as s:
                id_col = pk_column(self.model)
                stmt = select(self.model).where(
                    id_col == getattr(validated_data, pk_name(self.model))
                )
                row = s.execute(stmt).scalar_one()

                main_data = validated_data.model_dump(exclude_unset=True)
                m2m_data = pop_m2m_data(main_data, self.many_to_many_fields)
                main_data = json_none_as_sql_null(self.model, main_data, row)

                """Set only the fields present in the validated data."""
                for field_name, field_value in main_data.items():
                    if hasattr(row, field_name):
                        setattr(row, field_name, field_value)

                for field_name, selected_options in m2m_data.items():
                    relationship_name = self.many_to_many_fields[field_name][
                        "relationship"
                    ]
                    related_objects = load_related(
                        s, self.model, relationship_name, selected_options
                    )

                    getattr(row, relationship_name)[:] = related_objects

                s.add(row)
                s.commit()
                return handle_save_ok("UPDATE", self.model, row, self.get_session_key)

        except Exception as e:
            return handle_save_error(
                "UPDATE", self.model, validated_data.model_dump(), e
            )

    def save_sqlalchemy(self, updated: dict) -> tuple[bool, str]:
        """Original SQLAlchemy save logic"""
        with self.conn.session as s:
            try:
                id_col = pk_column(self.model)
                stmt = select(self.model).where(id_col == updated[pk_name(self.model)])
                row = s.execute(stmt).scalar_one()
                for k, v in json_none_as_sql_null(self.model, updated, row).items():
                    setattr(row, k, v)

                s.add(row)
                s.commit()
                return handle_save_ok("UPDATE", self.model, row)
            except Exception as e:
                updated_list = [f"{k}: {v}" for k, v in updated.items()]
                updated_str = ", ".join(updated_list)
                return handle_save_error("UPDATE", self.model, updated_str, e)

    def show(self) -> tuple[bool | None, str | None]:
        pretty_name = get_pretty_name(tablename(self.model))
        st.subheader(pretty_name)

        if self.update_schema:
            updated = self.get_pydantic_updates()
            if updated:
                return self.save_pydantic(updated)
        else:
            form_key = f"update_model_form_{pretty_name}_{self.key_prefix}"
            with st.form(form_key, border=False):
                updated = self.get_sqlalchemy_updates()
                update_btn = st.form_submit_button("Save")

            if update_btn:
                return self.save_sqlalchemy(updated)

        if self.update_show_many:
            one_to_many.show_rels(self.conn, self.model, self.row_id)

        return None, None

    def show_dialog(self) -> None:
        """Open the edit dialog with a form seeded from the database row."""
        self.reset_form_state()
        pretty_name = get_pretty_name(tablename(self.model))
        show_crud_dialog(f"Edit {pretty_name}", self.key, self.show)

    def reset_form_state(self) -> None:
        """Drop unsaved values a previously closed edit dialog left behind.

        Runs only on the opening run: reruns inside the open dialog skip it, so
        values entered there (e.g. after a validation error) are kept.
        """
        if self.update_schema:
            self.pydantic_ui.clear_session_data()
            st.session_state[self.get_session_key] = dict(self.current_values)
        else:
            self.input_fields.reset_state()
