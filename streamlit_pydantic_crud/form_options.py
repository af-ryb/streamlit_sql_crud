"""Load foreign-key and many-to-many options into a Pydantic CRUD form.

Shared by CreateRow and UpdateRow; failures are logged per field, shown once
as an ``st.warning``, and that field falls back to a plain input.
"""

import streamlit as st
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit.connections.sql_connection import SQLConnection

from streamlit_pydantic_crud.config_types import ForeignKeyOptions, ManyToManyFields
from streamlit_pydantic_crud.filters import custom_foreign_opts
from streamlit_pydantic_crud.pydantic_ui import PydanticCrudUi
from streamlit_pydantic_crud.sa_model import foreign_key_column_names, pk_name


def load_form_options(
    form: PydanticCrudUi,
    conn: SQLConnection,
    model: type[DeclarativeBase],
    foreign_key_options: ForeignKeyOptions,
    many_to_many_fields: ManyToManyFields,
    row: DeclarativeBase | None = None,
    dt_filters: dict | None = None,
    no_dt_filters: dict | None = None,
) -> None:
    """Fill `form` with the FK and M2M options configured for `model`.

    FK columns of `model` get options narrowed by the page filters, plus the
    current value of `row`; other configured fields run their raw query.
    """
    load_foreign_key_options(
        form, conn, model, foreign_key_options, row, dt_filters, no_dt_filters
    )
    load_many_to_many_options(form, conn, model, many_to_many_fields)


def load_foreign_key_options(
    form: PydanticCrudUi,
    conn: SQLConnection,
    model: type[DeclarativeBase],
    foreign_key_options: ForeignKeyOptions,
    row: DeclarativeBase | None = None,
    dt_filters: dict | None = None,
    no_dt_filters: dict | None = None,
) -> None:
    """Set the selectbox options of every ``foreign_key_options`` field."""
    fk_columns = foreign_key_column_names(model)
    for field_name, fk_config in foreign_key_options.items():
        try:
            display_field = fk_config["display_field"]
            value_field = fk_config["value_field"]
            with conn.session as session:
                if field_name in fk_columns:
                    fk_opts = custom_foreign_opts(
                        session,
                        field_name,
                        fk_config,
                        row=row,
                        dt_filters=dt_filters,
                        no_dt_filters=no_dt_filters,
                    )
                    options = [
                        {value_field: opt.idx, display_field: opt.name}
                        for opt in fk_opts
                    ]
                else:
                    rows = session.execute(fk_config["query"]).scalars().all()
                    options = [
                        {
                            value_field: getattr(opt_row, value_field),
                            display_field: getattr(opt_row, display_field),
                        }
                        for opt_row in rows
                    ]

            form.input_generator.set_foreign_key_options(
                field_name, options, display_field, value_field
            )
        except Exception:
            """Log and warn; the field falls back to a text input."""
            handle_option_load_error("foreign key", field_name)


def load_many_to_many_options(
    form: PydanticCrudUi,
    conn: SQLConnection,
    model: type[DeclarativeBase],
    many_to_many_fields: ManyToManyFields,
) -> None:
    """Set the multiselect options of every ``many_to_many_fields`` field."""
    for field_name, m2m_config in many_to_many_fields.items():
        try:
            relationship = getattr(model, m2m_config["relationship"])
            related_model = relationship.property.mapper.class_
            query = select(related_model)
            if "filter" in m2m_config:
                query = m2m_config["filter"](query)

            with conn.session as session:
                rows = session.execute(query).scalars().all()
                form.input_generator.set_many_to_many_options(
                    field_name,
                    list(rows),
                    m2m_config["display_field"],
                    pk_name(related_model),
                )
        except Exception:
            handle_option_load_error("many-to-many", field_name)


def handle_option_load_error(kind: str, field_name: str) -> None:
    """Log the current exception and warn the user about the field.

    Must be called from an ``except`` block. ``kind`` is ``"foreign key"`` or
    ``"many-to-many"``; the warning stays visible even with ``disable_log``.
    """
    logger.exception(f"Failed to load {kind} data for {field_name}")
    st.warning(f"Could not load {kind} options for '{field_name}'.")
