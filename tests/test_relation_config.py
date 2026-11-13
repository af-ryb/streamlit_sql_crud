"""`ForeignKeyField` / `ManyToManyField` config objects and the deprecated dict form.

Both forms must behave the same; only the dict form warns, once per relation
parameter of a public construction. The `_typing_*` functions are never
called: `ty check` covers them.
"""

import dataclasses
import os
import re
import warnings
from collections.abc import Callable
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import select
from streamlit.connections import SQLConnection
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud import (
    ForeignKeyField,
    ManyToManyField,
    PydanticCrudUi,
    SqlUi,
)
from streamlit_pydantic_crud.config_types import (
    ForeignKeyOptions,
    ManyToManyFields,
    ResolvedManyToManyField,
    resolve_foreign_key_options,
    resolve_many_to_many_fields,
)
from tests._apps.sqlmodel_models import Hero, HeroCreate, Power, Team
from tests.test_form_options import Post, Tag
from tests.test_sqlmodel import heroes, power_names

APP = str(Path(__file__).parent / "_apps" / "sqlmodel_app.py")
FORMS = ["object", "dict"]
M2M_MSG = r"Dict entries in 'many_to_many_fields' are deprecated since 0\.9\.1"
FK_MSG = r"Dict entries in 'foreign_key_options' are deprecated since 0\.9\.1"
TEAMS = select(Team)
Run = Callable[[str, str], tuple[AppTest, list[str]]]


def _version_picker_filter(q):
    return q.filter(Power.name != "laser")


def _typing_consumer_call(conn: SQLConnection) -> None:
    """The consumer call: an unannotated filter function, then a lambda."""
    SqlUi(
        conn=conn,
        model=Hero,
        many_to_many_fields={
            "powers": ManyToManyField(
                relationship="powers",
                display_field="name",
                filter=_version_picker_filter,
            ),
        },
        foreign_key_options={"team_id": ForeignKeyField(TEAMS, display_field="name")},
    )
    """A lambda body is checked against Select: use mapped columns (or col())."""
    SqlUi(
        conn=conn,
        model=Post,
        many_to_many_fields={
            "tag_ids": ManyToManyField(
                display_field="label",
                relationship="tags",
                filter=lambda q: q.filter(Tag.id > 1),
            ),
        },
    )
    PydanticCrudUi(
        schema=HeroCreate,
        key="f",
        many_to_many_fields={"powers": ManyToManyField(display_field="name")},
        foreign_key_options={
            "team_id": ForeignKeyField(query=TEAMS, display_field="name")
        },
    )


def _typing_dict_form_still_accepted(conn: SQLConnection) -> None:
    SqlUi(
        conn=conn,
        model=Hero,
        many_to_many_fields={
            "powers": {
                "relationship": "powers",
                "display_field": "name",
                "filter": _version_picker_filter,
            },
        },
        foreign_key_options={
            "team_id": {"query": TEAMS, "display_field": "name", "value_field": "id"}
        },
    )


def _typing_rejects_wrong_types() -> None:
    ManyToManyField(display_field=1)  # ty: ignore[invalid-argument-type]
    ForeignKeyField(query="teams", display_field="name")  # ty: ignore[invalid-argument-type]


def test_foreign_key_value_field_defaults_to_id() -> None:
    assert ForeignKeyField(query=TEAMS, display_field="name").value_field == "id"
    assert ForeignKeyField(TEAMS, "name", "code").value_field == "code"


def test_configs_are_frozen() -> None:
    config = ManyToManyField(display_field="name")
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.display_field = "other"  # ty: ignore[invalid-assignment]


def test_relationship_defaults_to_the_key() -> None:
    resolved = resolve_many_to_many_fields(
        {"powers": ManyToManyField(display_field="name")}
    )
    assert resolved == {
        "powers": ResolvedManyToManyField(display_field="name", relationship="powers")
    }


def test_explicit_relationship_is_honoured() -> None:
    config = ManyToManyField(
        display_field="name", relationship="powers", filter=_version_picker_filter
    )
    resolved = resolve_many_to_many_fields({"power_ids": config})["power_ids"]
    assert (resolved.relationship, resolved.display_field) == ("powers", "name")
    assert resolved.filter is _version_picker_filter


def test_objects_resolve_without_warning_and_are_idempotent() -> None:
    fk = {"team_id": ForeignKeyField(query=TEAMS, display_field="name")}
    m2m = {"powers": ManyToManyField(display_field="name")}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fk_once = resolve_foreign_key_options(fk)
        m2m_once = resolve_many_to_many_fields(m2m)
        fk_twice = resolve_foreign_key_options(fk_once)
        m2m_twice = resolve_many_to_many_fields(m2m_once)
    assert fk_twice["team_id"] is fk["team_id"]
    assert m2m_twice["powers"] is m2m_once["powers"]
    assert resolve_foreign_key_options(None) == {}
    assert resolve_many_to_many_fields(None) == {}


def test_dict_entries_resolve_to_the_same_objects() -> None:
    fk: ForeignKeyOptions = {"team_id": {"query": TEAMS, "display_field": "name"}}
    m2m: ManyToManyFields = {
        "powers": {"display_field": "name"},
        "power_ids": {
            "relationship": "powers",
            "display_field": "name",
            "filter": _version_picker_filter,
        },
    }
    with pytest.warns(DeprecationWarning, match=FK_MSG):
        resolved_fk = resolve_foreign_key_options(fk)
    with pytest.warns(DeprecationWarning, match=M2M_MSG) as caught:
        resolved_m2m = resolve_many_to_many_fields(m2m)

    assert len(caught) == 1
    assert resolved_fk == {"team_id": ForeignKeyField(TEAMS, "name", "id")}
    assert resolved_m2m == resolve_many_to_many_fields(
        {
            "powers": ManyToManyField(display_field="name"),
            "power_ids": ManyToManyField(
                "name", relationship="powers", filter=_version_picker_filter
            ),
        }
    )


def test_dict_warning_points_at_the_caller() -> None:
    with pytest.warns(DeprecationWarning, match=M2M_MSG) as caught:
        PydanticCrudUi(
            schema=HeroCreate,
            key="warn",
            many_to_many_fields={"powers": {"display_field": "name"}},
        )
    assert [w.filename for w in caught] == [__file__]


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Run:
    """Return a callable rendering the SQLModel harness with a relation form.

    It returns the app and the dict-form deprecations of that single script run.
    """
    monkeypatch.setenv("CRUD_TEST_DB", str(tmp_path / "relations.db"))
    monkeypatch.setenv("CRUD_TEST_MODE", "")
    monkeypatch.setenv("CRUD_TEST_RELATIONS", "")

    def _run(mode: str, form: str) -> tuple[AppTest, list[str]]:
        os.environ["CRUD_TEST_MODE"] = mode
        os.environ["CRUD_TEST_RELATIONS"] = form
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30)
        return at, rerun(at)

    return _run


def rerun(at: AppTest) -> list[str]:
    """Run the app once; return the dict-form deprecations of that run."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        at.run()
    assert not at.exception, [e.message for e in at.exception]
    return [
        str(w.message)
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and "Dict entries" in str(w.message)
    ]


def assert_warned(found: list[str], form: str) -> None:
    """The dict form warns once per relation parameter; objects never do."""
    patterns = [FK_MSG, M2M_MSG] if form == "dict" else []
    assert len(found) == len(patterns), found
    for pattern in patterns:
        assert sum(bool(re.search(pattern, message)) for message in found) == 1


def submit(at: AppTest) -> list[str]:
    """Submit the open form; return the deprecations of the rerun."""
    next(b for b in at.button if (b.key or "").startswith("FormSubmitter")).click()
    return rerun(at)


@pytest.mark.parametrize("form", FORMS)
def test_create_saves_fk_and_m2m(run: Run, form: str) -> None:
    at, found = run("create_schema", form)
    assert_warned(found, form)
    team = at.selectbox(key="cs_create_team_id")
    powers = at.multiselect(key="cs_create_powers")
    assert [team.format_func(o) for o in team.options] == ["Avengers", "X-Men"]
    assert [powers.format_func(o) for o in powers.options] == ["fly", "laser"]

    at.text_input(key="cs_create_name").input("Typed")
    team.select(2)
    powers.select(1).select(2)
    assert_warned(submit(at), form)

    hero = heroes(os.environ["CRUD_TEST_DB"])[13]
    assert (hero.name, hero.team_id) == ("Typed", 2)
    assert power_names(hero) == ["fly", "laser"]


@pytest.mark.parametrize("form", FORMS)
def test_edit_prefills_and_saves_m2m(run: Run, form: str) -> None:
    at, found = run("update_schema", form)
    assert_warned(found, form)
    assert at.multiselect(key="us_update_powers").value == []

    at.multiselect(key="us_update_powers").select(2)
    assert_warned(submit(at), form)
    assert power_names(heroes(os.environ["CRUD_TEST_DB"])[1]) == ["laser"]

    at, _ = run("update_schema", form)
    assert at.multiselect(key="us_update_powers").value == [2]


@pytest.mark.parametrize("form", FORMS)
def test_sql_ui_reads_m2m_and_opens_the_create_dialog(run: Run, form: str) -> None:
    """SqlUi -> CreateRow -> PydanticCrudUi: the dict form warns once, not thrice."""
    at, _ = run("update_schema", form)
    at.multiselect(key="us_update_powers").select(1)
    submit(at)

    at, found = run("table_m2m", form)
    assert_warned(found, form)
    shown = next(m.value for m in at.markdown if m.value.startswith("POWERS="))
    assert shown.startswith("POWERS={1: ['fly'], 2: [], ")

    at.button(key="m_stsql_action_add").click()
    assert_warned(rerun(at), form)
    team = at.selectbox(key="m_create_team_id")
    powers = at.multiselect(key="m_create_powers")
    assert [team.format_func(o) for o in team.options] == ["Avengers", "X-Men"]
    assert [powers.format_func(o) for o in powers.options] == ["fly", "laser"]
