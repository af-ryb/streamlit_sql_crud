"""CreateRow/UpdateRow in Pydantic mode (create_schema / update_schema).

Pydantic forms never use ExistingData/InputFields, so building them only costs
extra queries; FK options still follow the page filters on create only.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.config_types import ForeignKeyOptions
from streamlit_pydantic_crud.forms.options import ExistingData
from streamlit_pydantic_crud.forms.sa_fields import InputFields
from tests.conftest import Base, Department, Employee

FILTERS = {"name": "Dept 1"}


class EmployeeCreate(BaseModel):
    """Create schema for Employee."""

    name: str
    department_id: int


class EmployeeUpdate(BaseModel):
    """Update schema for Employee."""

    id: int
    name: str
    department_id: int


def _app(db: str, schema: bool) -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function
    from sqlalchemy import select  # noqa: PLC0415

    from streamlit_pydantic_crud.dialogs.create import (  # noqa: PLC0415
        CreateRow,
    )
    from streamlit_pydantic_crud.dialogs.edit import UpdateRow  # noqa: PLC0415
    from tests.conftest import Department, Employee  # noqa: PLC0415
    from tests.test_crud_pydantic_mode import (  # noqa: PLC0415
        FILTERS,
        EmployeeCreate,
        EmployeeUpdate,
    )

    conn = st.connection("sql", url=f"sqlite:///{db}")
    fk: ForeignKeyOptions = {
        "department_id": {
            "query": select(Department),
            "display_field": "name",
            "value_field": "id",
        }
    }
    create = CreateRow(
        conn,
        Employee,
        key="c",
        create_schema=EmployeeCreate if schema else None,
        foreign_key_options=fk,
        no_dt_filters=FILTERS,
    )
    update = UpdateRow(
        conn,
        Employee,
        1,
        key="u",
        update_schema=EmployeeUpdate if schema else None,
        foreign_key_options=fk,
        no_dt_filters=FILTERS,
    )
    if schema:
        for name, row in (("CREATE", create), ("UPDATE", update)):
            data = row.pydantic_ui.input_generator.foreign_key_data
            st.write(f"{name}={sorted(data['department_id']['options'])}")


@pytest.fixture
def db(tmp_path: Path) -> str:
    """SQLite file with three departments and one employee in Dept 1."""
    path = tmp_path / "pyd.db"
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(Department(id=i, name=f"Dept {i}") for i in range(1, 4))
        s.add(Employee(id=1, name="Emp 1", department_id=1, salary=1))
        s.commit()
    return str(path)


def _count_inits(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count ExistingData/InputFields constructions, wherever they are imported."""
    counts = {"ExistingData": 0, "InputFields": 0}
    for cls in (ExistingData, InputFields):
        monkeypatch.setattr(cls, "__init__", _counting(cls.__init__, cls, counts))
    return counts


def _counting(original: Any, cls: type, counts: dict[str, int]) -> Any:
    """Return an ``__init__`` that bumps ``counts[cls.__name__]`` then delegates."""

    def init(self: Any, *args: Any, **kwargs: Any) -> None:
        counts[cls.__name__] += 1
        original(self, *args, **kwargs)

    return init


def test_pydantic_mode_skips_existing_data_and_input_fields(
    db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts = _count_inits(monkeypatch)
    at = AppTest.from_function(_app, kwargs={"db": db, "schema": True}).run()
    assert not at.exception
    assert counts == {"ExistingData": 0, "InputFields": 0}


def test_sqlalchemy_mode_builds_existing_data_and_input_fields(
    db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts = _count_inits(monkeypatch)
    at = AppTest.from_function(_app, kwargs={"db": db, "schema": False}).run()
    assert not at.exception
    assert counts == {"ExistingData": 2, "InputFields": 2}


def test_pydantic_mode_fk_options_follow_filters_on_create_only(db: str) -> None:
    at = AppTest.from_function(_app, kwargs={"db": db, "schema": True}).run()
    assert not at.exception
    lines = dict(m.value.split("=", 1) for m in at.markdown)
    assert lines["CREATE"] == "[1]"
    assert lines["UPDATE"] == "[1, 2, 3]"
