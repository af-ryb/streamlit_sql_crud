"""Page filters narrow FK options only when creating, not editing (L2).

Filters match related models by column name (``Department.name`` here), so
an edit dialog could hide the department the user wants to move a row to.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from tests.conftest import Base, Department, Employee

FILTERS = {"name": "Dept 1"}


def _app(db: str) -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud.create_delete_model import (  # noqa: PLC0415
        CreateRow,
    )
    from streamlit_pydantic_crud.state import UPDATED_KEY, set_state  # noqa: PLC0415
    from streamlit_pydantic_crud.update_model import UpdateRow  # noqa: PLC0415
    from tests.conftest import Employee  # noqa: PLC0415
    from tests.test_fk_filters_edit import FILTERS  # noqa: PLC0415

    set_state(UPDATED_KEY, 0)
    conn = st.connection("sql", url=f"sqlite:///{db}")
    create = CreateRow(conn, Employee, key="c", no_dt_filters=FILTERS)
    update = UpdateRow(conn, Employee, 1, key="u", no_dt_filters=FILTERS)
    for name, row in (("CREATE", create), ("UPDATE", update)):
        idxs = sorted(opt.idx for opt in row.existing_data.fk["department_id"])
        st.write(f"{name}={idxs}")


def test_update_fk_options_ignore_page_filters(tmp_path: Path) -> None:
    db = tmp_path / "fk.db"
    eng = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(Department(id=i, name=f"Dept {i}") for i in range(1, 4))
        s.add(Employee(id=1, name="Emp 1", department_id=1, salary=1))
        s.commit()

    at = AppTest.from_function(_app, kwargs={"db": str(db)}).run()
    assert not at.exception
    lines = dict(m.value.split("=", 1) for m in at.markdown)
    assert lines["CREATE"] == "[1]"
    assert lines["UPDATE"] == "[1, 2, 3]"
