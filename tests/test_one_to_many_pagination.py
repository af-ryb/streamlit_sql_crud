"""The one-to-many panel pages its child rows with the shared pager.

Its pager key does not include the parent id, so switching to a parent with
fewer children must clamp the stored page. A create or delete in the panel
refreshes its rows and count, which are cached per data version.
"""

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.dialogs.one_to_many import ReadManyRel
from streamlit_pydantic_crud.state import bump_data_version

SUFFIX = "parent_parent_id_child"
PAGE = f"stsql_read_many_pag_{SUFFIX}_pagination"
DF = f"stsql_many_df_{SUFFIX}"
CREATE = f"stsql_create_many_{SUFFIX}"
DELETE = f"st_sql_many_delete_{SUFFIX}_delete_del_btn"


class Base(DeclarativeBase):
    """Declarative base mirroring the harness models."""


class Parent(Base):
    """Parent row owning the children."""

    __tablename__ = "parent"

    id: Mapped[int] = mapped_column(primary_key=True)
    children: Mapped[list["Child"]] = relationship()


class Child(Base):
    """Child row pointing at its parent."""

    __tablename__ = "child"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id"))


def child_ids(at: AppTest) -> list[int]:
    """Return the child ids shown in the panel's Read tab."""
    return at.dataframe[0].value.index.to_list()


@pytest.fixture
def app(run_app: Callable[[str], AppTest]) -> AppTest:
    """Render the panel of parent 1 (120 children)."""
    at = run_app("one_to_many_app.py")
    assert not at.exception
    return at


def test_panel_pages_children(app: AppTest) -> None:
    assert app.pagination(key=PAGE).proto.num_pages == 3
    assert child_ids(app)[0] == 1

    app.pagination(key=PAGE).set_value(2).run()

    assert child_ids(app)[0] == 51
    assert any(c.value == "51-100 / 120" for c in app.caption)


def test_panel_page_clamps_for_smaller_parent(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(3).run()
    app.session_state["PARENT"] = 2
    app.run()

    assert not app.exception
    assert app.pagination(key=PAGE).value == 1
    assert child_ids(app) == list(range(121, 131))


def test_delete_refreshes_read_tab(app: AppTest) -> None:
    app.session_state["SELECT"] = (f"{DF}_0", [0, 1])
    app.run()
    app.button(key=DELETE).click().run()

    assert not app.exception
    assert any("Successfully deleted 2" in s.value for s in app.success)
    assert child_ids(app)[:2] == [3, 4]
    assert any(c.value == "1-50 / 118" for c in app.caption)
    assert not [b for b in app.button if b.key == DELETE]


def test_create_refreshes_read_tab(app: AppTest) -> None:
    name = app.selectbox(key=f"{CREATE}_0_create_name")
    name.set_value(name.options[0])
    app.button[0].click().run()

    assert not app.exception
    assert any(c.value == "1-50 / 121" for c in app.caption)


def test_count_is_cached_per_data_version(app: AppTest, tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "crud.db") as db:
        db.execute("INSERT INTO child (id, name, parent_id) VALUES (500, 'X', 1)")
    app.run()
    assert any(c.value == "1-50 / 120" for c in app.caption)

    bump_data_version()
    app.run()
    assert any(c.value == "1-50 / 121" for c in app.caption)


def test_pages_are_ordered_by_pk() -> None:
    rel = ReadManyRel(Parent, 1, Parent.children.property)

    sql = str(rel.get_stmt_pag(50, 2))

    assert "ORDER BY child.id" in sql
