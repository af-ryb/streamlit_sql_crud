"""SqlUi and the CRUD dialogs over SQLModel table models.

SQLModel classes have no `registry` attribute and their `str` columns use
`AutoString`, a TypeDecorator without `python_type`; both used to break.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import streamlit as st
from sqlmodel import Session, create_engine, select
from streamlit.testing.v1 import AppTest

from tests._apps.sqlmodel_models import Hero

APP = str(Path(__file__).parent / "_apps" / "sqlmodel_app.py")


@pytest.fixture
def db(tmp_path: Path) -> str:
    """Path of the SQLite file the harness app seeds."""
    return str(tmp_path / "sqlmodel.db")


@pytest.fixture
def run(db: str, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], AppTest]:
    """Return a callable rendering the SQLModel harness app in a scenario."""
    monkeypatch.setenv("CRUD_TEST_DB", db)

    def _run(mode: str) -> AppTest:
        os.environ["CRUD_TEST_MODE"] = mode
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30).run()
        assert not at.exception, [e.message for e in at.exception]
        return at

    monkeypatch.setenv("CRUD_TEST_MODE", "")
    return _run


def line(at: AppTest, prefix: str) -> str:
    """Return the value printed by the app after `prefix=`."""
    return next(
        m.value.removeprefix(f"{prefix}=")
        for m in at.markdown
        if m.value.startswith(f"{prefix}=")
    )


def submit(at: AppTest) -> AppTest:
    """Click the form submit button and rerun the app."""
    button = next(b for b in at.button if (b.key or "").startswith("FormSubmitter"))
    button.click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def heroes(db: str) -> dict[int, Hero]:
    """Load every hero with its powers from the harness database."""
    with Session(create_engine(f"sqlite:///{db}")) as s:
        rows = s.exec(select(Hero)).all()
        for row in rows:
            _ = row.powers
        return {row.id: row for row in rows if row.id is not None}


def power_names(hero: Hero) -> list[str]:
    """Sorted names of the hero's powers."""
    return sorted(p.name for p in hero.powers)


@pytest.mark.parametrize(("mode", "key"), [("table_plain", "p"), ("table_schema", "s")])
def test_table_reads_rows(run: Callable[[str], AppTest], mode: str, key: str) -> None:
    at = run(mode)
    assert line(at, "QTTY") == "12"
    cols = line(at, "COLS").split(",")
    assert {"id", "name", "rank", "team_id"} <= set(cols)
    assert ("meta" in cols) is (mode == "table_plain")
    assert at.dataframe(key=f"{key}_df_sql_ui_0").value["name"].iloc[0] == "H1"


@pytest.mark.parametrize(("mode", "key"), [("table_plain", "p"), ("table_schema", "s")])
def test_string_column_is_filterable(
    run: Callable[[str], AppTest], mode: str, key: str
) -> None:
    at = run(mode)
    name_filter = at.selectbox(key=f"{key}_create_no_dt_filter_Name")
    assert "H2" in name_filter.options
    name_filter.select("H2").run()
    assert line(at, "QTTY") == "1"


def test_create_plain(run: Callable[[str], AppTest], db: str) -> None:
    at = run("create_plain")
    at.selectbox(key="cp_create_name").select("H5")
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    assert heroes(db)[13].name == "H5"


def test_create_schema(run: Callable[[str], AppTest], db: str) -> None:
    at = run("create_schema")
    at.text_input(key="cs_create_name").input("Schema New")
    at.selectbox(key="cs_create_team_id").select(2)
    at.multiselect(key="cs_create_powers").select(1).select(2)
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    hero = heroes(db)[13]
    assert (hero.name, hero.team_id) == ("Schema New", 2)
    assert power_names(hero) == ["fly", "laser"]


def test_update_plain(run: Callable[[str], AppTest], db: str) -> None:
    at = run("update_plain")
    name = at.selectbox(key="up_update_name")
    assert name.value == "H1"
    name.select("H3")
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    assert heroes(db)[1].name == "H3"


def test_update_schema(run: Callable[[str], AppTest], db: str) -> None:
    at = run("update_schema")
    at.text_input(key="us_update_name").input("H1 schema")
    at.multiselect(key="us_update_powers").select(2)
    submit(at)
    assert line(at, "RESULT").startswith("True|")
    hero = heroes(db)[1]
    assert hero.name == "H1 schema"
    assert power_names(hero) == ["laser"]


def test_delete(run: Callable[[str], AppTest], db: str) -> None:
    at = run("delete")
    at.button(key="d_delete_del_btn").click().run()
    assert line(at, "RESULT").startswith("True|")
    assert 3 not in heroes(db)
    assert len(heroes(db)) == 11
