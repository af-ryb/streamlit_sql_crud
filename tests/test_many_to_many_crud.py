"""Many-to-many persistence through CreateRow / UpdateRow in Pydantic mode."""

from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from tests.test_form_options import Author, Base, Post, Tag, tag_link


class PostCreate(BaseModel):
    """Create schema for Post."""

    title: str
    author_id: int
    tag_ids: list[int]


class PostUpdate(BaseModel):
    """Update schema for Post."""

    id: int
    title: str
    author_id: int
    tag_ids: list[int]


def _app(db: str, action: str, tag_ids: list[int]) -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud.config_types import (  # noqa: PLC0415
        ManyToManyFields,
    )
    from streamlit_pydantic_crud.dialogs.create import (  # noqa: PLC0415
        CreateRow,
    )
    from streamlit_pydantic_crud.dialogs.edit import UpdateRow  # noqa: PLC0415
    from tests.test_form_options import Post  # noqa: PLC0415
    from tests.test_many_to_many_crud import (  # noqa: PLC0415
        PostCreate,
        PostUpdate,
    )

    conn = st.connection("sql", url=f"sqlite:///{db}")
    m2m: ManyToManyFields = {
        "tag_ids": {"relationship": "tags", "display_field": "label"}
    }
    if action == "create":
        create = CreateRow(
            conn, Post, key="c", create_schema=PostCreate, many_to_many_fields=m2m
        )
        ok, _msg = create.save_pydantic(
            PostCreate(title="new", author_id=1, tag_ids=tag_ids)
        )
        st.write(f"OK={ok}")
        return
    update = UpdateRow(
        conn, Post, 1, key="u", update_schema=PostUpdate, many_to_many_fields=m2m
    )
    st.write(f"PREFILL={st.session_state[update.get_session_key]['tag_ids']}")
    if action == "update":
        ok, _msg = update.save_pydantic(
            PostUpdate(id=1, title="p", author_id=1, tag_ids=tag_ids)
        )
        st.write(f"OK={ok}")


@pytest.fixture
def db(tmp_path: Path) -> str:
    """SQLite file with an author, three tags and post 1 tagged with 1 and 2."""
    path = tmp_path / "m2m.db"
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Author(id=1, name="A1"))
        s.add_all(Tag(id=i, label=f"T{i}") for i in range(1, 4))
        s.flush()
        tags = list(s.scalars(select(Tag).where(Tag.id.in_([1, 2]))))
        s.add(Post(id=1, title="p", author_id=1, tags=tags))
        s.commit()
    return str(path)


def _links(db: str) -> set[tuple[int, int]]:
    """Return every (post_id, tag_id) association row."""
    with Session(create_engine(f"sqlite:///{db}")) as s:
        rows = s.execute(select(tag_link.c.post_id, tag_link.c.tag_id)).all()
    return {(r[0], r[1]) for r in rows}


def _texts(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown]


def _app_test(db: str, action: str, tag_ids: list[int]) -> AppTest:
    kwargs = {"db": db, "action": action, "tag_ids": tag_ids}
    return AppTest.from_function(_app, kwargs=kwargs).run()


def test_create_persists_selected_tags(db: str) -> None:
    at = _app_test(db, "create", [1, 3])

    assert not at.exception
    assert "OK=True" in _texts(at)
    assert _links(db) == {(1, 1), (1, 2), (2, 1), (2, 3)}


def test_update_form_prefills_current_tags(db: str) -> None:
    at = _app_test(db, "prefill", [])

    assert not at.exception
    assert "PREFILL=[1, 2]" in _texts(at)


def test_update_changes_tag_associations(db: str) -> None:
    at = _app_test(db, "update", [2, 3])

    assert not at.exception
    assert "OK=True" in _texts(at)
    assert _links(db) == {(1, 2), (1, 3)}


def test_update_with_no_tags_clears_associations(db: str) -> None:
    at = _app_test(db, "update", [])

    assert "OK=True" in _texts(at)
    assert _links(db) == set()
