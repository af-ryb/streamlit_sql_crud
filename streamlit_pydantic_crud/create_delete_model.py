import streamlit as st
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.filters import ExistingData
from streamlit_pydantic_crud.input_fields import InputFields
from streamlit_pydantic_crud.lib import (
    CACHE_TTL_SECONDS,
    format_database_error,
    get_pretty_name,
    log,
    set_state,
)
from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi
from streamlit_pydantic_crud.state import get_ui_state
from streamlit_pydantic_crud.utils import pk_attr, pk_column, pk_name, tablename


class CreateRow:
    def __init__(
        self,
        conn: SQLConnection,
        model: type[DeclarativeBase],
        default_values: dict | None = None,
        key: str = "create",
        create_schema: type[BaseModel] | None = None,
        foreign_key_options: dict | None = None,
        many_to_many_fields: dict | None = None,
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

        set_state("stsql_updated", 0)

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

        # Initialize PydanticUi if schema provided
        if self.create_schema:
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

            # Load foreign key data for fields that need it
            self._load_foreign_key_data()
            self._load_many_to_many_data()

    def get_fields(self):
        if self.create_schema:
            return self.get_pydantic_fields()
        return self.get_sqlalchemy_fields()

    def get_pydantic_fields(self):
        """Generate fields using PydanticUi"""
        # Use PydanticUi to render the form with submit button
        form_data, submitted = self.pydantic_ui.render_with_submit("Save")
        return form_data if submitted else None

    def _load_many_to_many_data(self):
        """Load many-to-many relationship data from the database."""
        for field_name, m2m_config in self.many_to_many_fields.items():
            try:
                relationship_name = m2m_config["relationship"]
                display_field = m2m_config["display_field"]

                # Get the related model from the relationship
                related_model = getattr(
                    self.model, relationship_name
                ).property.mapper.class_

                # Base query for the related model
                query = select(related_model)

                # Apply optional filter
                if "filter" in m2m_config:
                    query = m2m_config["filter"](query)

                with self.conn.session as session:
                    rows = session.execute(query).scalars().all()

                    # Set options in PydanticUi's input generator
                    self.pydantic_ui.input_generator.set_many_to_many_options(
                        field_name, list(rows), display_field, pk_name(related_model)
                    )

            except Exception:
                logger.exception(f"Failed to load many-to-many data for {field_name}")

    def _load_foreign_key_data(self):
        """Load foreign key data from database for form fields using filtered options."""
        for field_name, fk_config in self.foreign_key_options.items():
            try:
                display_field = fk_config["display_field"]
                value_field = fk_config["value_field"]

                # Use filtered foreign key options from ExistingData instead of raw query
                if (
                    hasattr(self.existing_data, "fk")
                    and field_name in self.existing_data.fk
                ):
                    fk_opts = self.existing_data.fk[field_name]

                    # Convert FkOpt objects to list of dicts for the input generator
                    options = [
                        {value_field: fk_opt.idx, display_field: fk_opt.name}
                        for fk_opt in fk_opts
                    ]

                else:
                    # Fallback to original logic if filtered options not available
                    query = fk_config["query"]

                    with self.conn.session as session:
                        rows = session.execute(query).scalars().all()

                        # Convert to list of dicts for the input generator
                        options = []
                        for row in rows:
                            options.append(
                                {
                                    value_field: getattr(row, value_field),
                                    display_field: getattr(row, display_field),
                                }
                            )

                # Set the options in the input generator
                self.pydantic_ui.input_generator.set_foreign_key_options(
                    field_name, options, display_field, value_field
                )

            except Exception:
                # Log full traceback but continue - field falls back to text input
                logger.exception(f"Failed to load foreign key data for {field_name}")

    def get_sqlalchemy_fields(self):
        """Original SQLAlchemy field generation logic"""
        cols = self.model.__table__.columns
        created = {}
        for col in cols:
            col_name = col.description or col.name
            if col_name is None:
                continue

            initial_value = self.initial_data.get(col_name)

            if col_name in self.default_values:
                input_value = self.default_values[col_name]
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

    def save_pydantic(self, validated_data: BaseModel):
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
                ss.stsql_updated += 1
                table_name = tablename(self.model)
                log("CREATE", table_name, row)

                # Clear the form data after successful save
                session_key = f"{self.key_prefix}_form_data"
                if session_key in st.session_state:
                    del st.session_state[session_key]

                return True, f"Created successfully {row}"

        except Exception as e:
            ss.stsql_updated += 1
            table_name = tablename(self.model)
            log("CREATE", table_name, validated_data.model_dump(), success=False)
            logger.exception(f"Create failed for {table_name}")

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
                table_name = tablename(self.model)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
        except Exception as e:
            ss.stsql_updated += 1
            table_name = tablename(self.model)
            log("CREATE", table_name, created, success=False)
            logger.exception(f"Create failed for {table_name}")

            # Handle specific SQLAlchemy errors with user-friendly messages
            error_msg = format_database_error(e)
            return False, error_msg

    def show_dialog(self):
        pretty_name = get_pretty_name(tablename(self.model))

        @st.dialog(f"Create {pretty_name}", width="large")
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ui_state = get_ui_state(self.key)
            ui_state.update_ok = status
            ui_state.update_message = msg
            ui_state.opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()


class DeleteRows:
    def __init__(
        self,
        conn: SQLConnection,
        model: type[DeclarativeBase],
        rows_id: list[int],
        key: str,
    ) -> None:
        self.conn = conn
        self.model = model
        self.rows_id = rows_id
        self.key = key
        self.key_prefix = f"{key}_delete"

    @st.cache_data(ttl=CACHE_TTL_SECONDS)
    def get_rows_str(_self, table_name: str, rows_id: list[int], updated: int):
        """Return the string form of the rows to delete.

        `table_name` and the `updated` counter are cache-key inputs only.
        """
        id_col = pk_column(_self.model)
        stmt = select(_self.model).where(id_col.in_(rows_id))

        with _self.conn.session as s:
            rows = s.execute(stmt).scalars()
            rows_str = [str(row) for row in rows]

        return rows_str

    def show(self, pretty_name):
        st.subheader("Delete selected items?")

        table_name = tablename(self.model)
        updated = ss.get("stsql_updated", 0)
        rows_str = self.get_rows_str(table_name, self.rows_id, updated)
        st.dataframe({pretty_name: rows_str}, hide_index=True)

        btn = st.button("Delete", key=f"{self.key_prefix}_del_btn")
        if not btn:
            return None, None

        lancs: list[str] = []
        missing: list[int] = []
        with self.conn.session as s:
            try:
                for row_id in self.rows_id:
                    lanc = s.get(self.model, row_id)
                    if lanc is None:
                        missing.append(row_id)
                        continue
                    lancs.append(str(lanc))
                    s.delete(lanc)

                s.commit()
                ss.stsql_updated += 1
            except Exception as e:
                ss.stsql_updated += 1
                log("DELETE", table_name, self.rows_id, success=False)
                logger.exception(f"Delete failed for {table_name}")
                return False, format_database_error(e)

        missing_msg = f"Not found (already deleted?): {missing}" if missing else ""
        if not lancs:
            return False, missing_msg

        log("DELETE", table_name, ", ".join(lancs))
        msg = f"Successfully deleted {len(lancs)}"
        return True, f"{msg}. {missing_msg}" if missing else msg

    def show_dialog(self):
        pretty_name = get_pretty_name(tablename(self.model))

        @st.dialog(f"Delete {pretty_name}", width="large")
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ui_state = get_ui_state(self.key)
            ui_state.update_ok = status
            ui_state.update_message = msg
            ui_state.opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()
