"""Harness app copying a row of a JOIN read query through the real dialog.

`CRUD_TEST_MODE`: `schema` reads through a `read_schema` without the FK field
and with a many-to-many field (the consumer's alert table), `columns` selects
columns without the FK (the example's Projects page); a `_plain` suffix drops
the `create_schema`. Session
state `SELECT` (row positions) is reported as the dataframe selection.
"""

import os
from typing import Any
from unittest.mock import patch

import streamlit as st
from sqlalchemy import create_engine, select
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud import ForeignKeyField, ManyToManyField, SqlUi
from tests._apps.copy_fk_models import (
    Alert,
    AlertCreate,
    AlertRead,
    Template,
    seed,
)

DB = os.environ["CRUD_TEST_DB"]
MODE = os.environ.get("CRUD_TEST_MODE", "schema")

seed(create_engine(f"sqlite:///{DB}"))
conn = st.connection("sql", url=f"sqlite:///{DB}")
real_dataframe = DeltaGenerator.dataframe


def fake_dataframe(self: DeltaGenerator, *args: Any, **kwargs: Any) -> Any:
    """Render the table; report the `SELECT` positions as its selection."""
    result = real_dataframe(self, *args, **kwargs)
    rows = st.session_state.get("SELECT")
    if rows is None:
        return result
    return {"selection": {"rows": rows, "columns": []}}


M2M = {"rules": ManyToManyField(display_field="rule_name")}
LABELS = (Template.app_name.label("app_name"), Template.platform.label("platform"))
ON = Alert.template_id == Template.id
if MODE.startswith("schema"):
    stmt = select(Alert, *LABELS).join(Template, ON)
else:
    stmt = select(Alert.id, Alert.fact_query, *LABELS).join(Template, ON)

with patch.object(DeltaGenerator, "dataframe", fake_dataframe):
    SqlUi(
        conn=conn,
        read_instance=stmt,
        edit_create_model=Alert,
        read_schema=AlertRead if MODE.startswith("schema") else None,
        create_schema=None if MODE.endswith("_plain") else AlertCreate,
        foreign_key_options={
            "template_id": ForeignKeyField(
                query=select(Template), display_field="display_name"
            )
        },
        many_to_many_fields=M2M if MODE.startswith("schema") else None,
        available_filter=["app_name", "platform"],
        key="alert",
    )
