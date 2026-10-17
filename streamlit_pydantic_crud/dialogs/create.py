"""The create dialog: a form for a new row, in SQLAlchemy or Pydantic mode."""

from functools import partial
from typing import Any

import streamlit as st
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.config_types import ForeignKeyOptions, ManyToManyFields
from streamlit_pydantic_crud.db_errors import format_database_error
from streamlit_pydantic_crud.dialogs.frame import show_crud_dialog
from streamlit_pydantic_crud.display import get_pretty_name
from streamlit_pydantic_crud.form_options import ExistingData, load_form_options
from streamlit_pydantic_crud.input_fields import NO_INPUT, InputFields
from streamlit_pydantic_crud.logs import log
from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi
from streamlit_pydantic_crud.sa_model import (
    column_label,
    pk_attr,
    pk_name,
    tablename,
)
from streamlit_pydantic_crud.state import UPDATED_KEY, set_state


class CreateRow:
    """Create dialog for one new row, optionally seeded from a copied row."""

    def __init__(
        self,
        conn: SQLConnection,
        model: type[DeclarativeBase],
        default_values: dict | None = None,
        key: str = "create",
        create_schema: type[BaseModel] | None = None,
        foreign_key_options: ForeignKeyOptions | None = None,
        many_to_many_fields: ManyToManyFields | None = None,
        initial_data: dict | None = None,
        dt_filters: dict | None = None,
        no_dt_filters: dict | None = None,
    ) -> None:
        self.conn = conn
        self.model = model
        self.create_schema = create_schema
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        self.initial_data = initial_data or {}
        self.dt_filters = dt_filters or {}
        self.no_dt_filters = no_dt_filters or {}

        self.default_values = default_values or {}
        self.key = key
        self.key_prefix = f"{key}_create"

        set_state(UPDATED_KEY, 0)

        if not self.create_schema:
            """SQLAlchemy-mode inputs; Pydantic forms never read them."""
            with conn.session as s:
                self.existing_data = ExistingData(
                    s,
                    model,
                    self.default_values,
                    foreign_key_options=self.foreign_key_options,
                    dt_filters=self.dt_filters,
                    no_dt_filters=self.no_dt_filters,
                )
                self.input_fields = InputFields(
                    model,
                    key_prefix=self.key_prefix,
                    default_values=self.default_values,
                    existing_data=self.existing_data,
                )
            return

        session_key = f"{self.key_prefix}_form_data"

        # Pre-populate form with initial_data if provided (for "copy" action)
        if self.initial_data:
            # Remove the primary key to avoid conflicts, as it's a new record
            self.initial_data.pop(pk_name(self.model), None)
            set_state(session_key, self.initial_data)

        self.pydantic_ui = PydanticCrudUi(
            schema=self.create_schema,
            key=self.key_prefix,
            session_state_key=session_key,
            foreign_key_options=self.foreign_key_options,
            many_to_many_fields=self.many_to_many_fields,
            pk_name=pk_name(self.model),
        )

        # Set operation type to 'create' for proper empty value handling
        self.pydantic_ui.set_operation_type("create")

        load_form_options(
            self.pydantic_ui,
            conn,
            model,
            self.foreign_key_options,
            self.many_to_many_fields,
            dt_filters=self.dt_filters,
            no_dt_filters=self.no_dt_filters,
        )

    def get_pydantic_fields(self) -> BaseModel | None:
        """Generate fields using PydanticUi"""
        # Use PydanticUi to render the form with submit button
        form_data, submitted = self.pydantic_ui.render_with_submit("Save")
        return form_data if submitted else None

    def get_sqlalchemy_fields(self) -> dict[str, Any]:
        """Original SQLAlchemy field generation logic"""
        cols = self.model.__table__.columns
        created = {}
        for col in cols:
            col_name = column_label(col)
            if col_name is None:
                continue

            initial_value = self.initial_data.get(col_name)

            if col_name in self.default_values:
                input_value = self.default_values[col_name]
            else:
                input_value = self.input_fields.get_input_value(col, initial_value)

            if input_value is not NO_INPUT:
                created[col_name] = input_value

        return created

    def show(self, pretty_name: str) -> tuple[bool | None, str | None]:
        st.subheader(pretty_name)

        if self.create_schema:
            # Use PydanticUi which handles forms internally
            created = self.get_pydantic_fields()
            if created:
                return self.save_pydantic(created)
            return None, None
        # Use traditional form for SQLAlchemy-only mode
        with st.form(
            f"create_model_form_{pretty_name}_{self.key_prefix}", border=False
        ):
            created = self.get_sqlalchemy_fields()
            create_btn = st.form_submit_button("Save", type="primary")

        if create_btn:
            return self.save_sqlalchemy(created)
        return None, None

    def save_pydantic(self, validated_data: BaseModel) -> tuple[bool, str]:
        """Save using pre-validated Pydantic data from PydanticUi"""
        try:
            with self.conn.session as s:
                # Separate many-to-many fields from the main data
                m2m_data = {}
                main_data = validated_data.model_dump()

                for field_name in self.many_to_many_fields:
                    if field_name in main_data:
                        m2m_data[field_name] = main_data.pop(field_name)

                # Create the main object without m2m fields
                row = self.model(**main_data)
                s.add(row)
                s.flush()  # Flush to get the ID of the new row

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

                    # Append the related objects to the relationship
                    getattr(row, relationship_name).extend(related_objects)

                s.commit()
                ss[UPDATED_KEY] += 1
                table_name = tablename(self.model)
                log("CREATE", table_name, row)

                # Clear the form data after successful save
                session_key = f"{self.key_prefix}_form_data"
                if session_key in st.session_state:
                    del st.session_state[session_key]

                return True, f"Created successfully {row}"

        except Exception as e:
            ss[UPDATED_KEY] += 1
            table_name = tablename(self.model)
            log("CREATE", table_name, validated_data.model_dump(), success=False)
            logger.exception(f"Create failed for {table_name}")

            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg

    def save_sqlalchemy(self, created: dict) -> tuple[bool, str]:
        """Original SQLAlchemy save logic"""
        try:
            row = self.model(**created)
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss[UPDATED_KEY] += 1
                table_name = tablename(self.model)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
        except Exception as e:
            ss[UPDATED_KEY] += 1
            table_name = tablename(self.model)
            log("CREATE", table_name, created, success=False)
            logger.exception(f"Create failed for {table_name}")

            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg

    def show_dialog(self) -> None:
        """Open the create dialog with a form seeded from defaults or the copy."""
        self.reset_form_state()
        pretty_name = get_pretty_name(tablename(self.model))
        show_crud_dialog(
            f"Create {pretty_name}", self.key, partial(self.show, pretty_name)
        )

    def reset_form_state(self) -> None:
        """Drop unsaved values a previously closed create dialog left behind.

        Runs only on the opening run: reruns inside the open dialog skip it, so
        values entered there (e.g. after a validation error) are kept.
        """
        if self.create_schema:
            self.pydantic_ui.clear_session_data()
            session_key = f"{self.key_prefix}_form_data"
            st.session_state[session_key] = dict(self.initial_data)
        else:
            self.input_fields.reset_state()
