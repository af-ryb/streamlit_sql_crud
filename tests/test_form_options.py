"""Shared FK / many-to-many option loading for Pydantic CRUD forms."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from loguru import logger
from sqlalchemy import Column, Engine, ForeignKey, Table, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)
from sqlalchemy.pool import StaticPool
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.config_types import (
    ForeignKeyConfig,
    ForeignKeyOptions,
    ManyToManyFields,
)
from streamlit_pydantic_crud.form_options import (
    load_form_options,
)
from streamlit_pydantic_crud.sa_model import foreign_key_column_names


class Base(DeclarativeBase):
    """Declarative base for the form-option models."""


tag_link = Table(
    "post_tag",
    Base.metadata,
    Column("post_id", ForeignKey("post.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class Author(Base):
    """FK target of Post."""

    __tablename__ = "author"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class Tag(Base):
    """Many-to-many target of Post."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column()


class Post(Base):
    """Row with one FK column and one many-to-many relationship."""

    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    tags: Mapped[list[Tag]] = relationship(secondary=tag_link)


class FakeConn:
    """Stand-in for SQLConnection: `.session` opens a new Session per use."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @property
    def session(self) -> Session:
        """Return a fresh Session, used as a context manager by the loaders."""
        return Session(self.engine)


AUTHOR_FK: ForeignKeyConfig = {
    "query": select(Author),
    "display_field": "name",
    "value_field": "id",
}


@pytest.fixture
def conn() -> Iterator[Any]:
    """FakeConn over an in-memory DB with three authors and three tags."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(Author(id=i, name=f"A{i}") for i in range(1, 4))
        s.add_all(Tag(id=i, label=f"T{i}") for i in range(1, 4))
        s.commit()
    yield FakeConn(eng)
    eng.dispose()


def test_foreign_key_column_names() -> None:
    assert foreign_key_column_names(Post) == {"author_id"}


def test_fk_column_options_follow_filters_and_keep_row_value(conn: Any) -> None:
    """FK columns are filtered, yet the edited row's current value stays listed."""
    form = MagicMock()
    fk: ForeignKeyOptions = {"author_id": AUTHOR_FK}
    row = Post(id=1, title="p", author_id=3)

    load_form_options(form, conn, Post, fk, {}, row=row, no_dt_filters={"name": "A1"})

    form.input_generator.set_foreign_key_options.assert_called_once_with(
        "author_id", [{"id": 1, "name": "A1"}, {"id": 3, "name": "A3"}], "name", "id"
    )


def test_non_fk_field_runs_raw_query(conn: Any) -> None:
    """A configured field that is not an FK column ignores the page filters."""
    form = MagicMock()
    fk: ForeignKeyOptions = {"writer": AUTHOR_FK}

    load_form_options(form, conn, Post, fk, {}, no_dt_filters={"name": "A1"})

    options = form.input_generator.set_foreign_key_options.call_args.args[1]
    assert [opt["id"] for opt in options] == [1, 2, 3]


def test_many_to_many_options_apply_filter(conn: Any) -> None:
    form = MagicMock()
    m2m: ManyToManyFields = {
        "tag_ids": {
            "relationship": "tags",
            "display_field": "label",
            "filter": lambda q: q.where(Tag.id > 1),
        }
    }

    load_form_options(form, conn, Post, {}, m2m)

    args = form.input_generator.set_many_to_many_options.call_args.args
    assert args[0] == "tag_ids"
    assert [tag.id for tag in args[1]] == [2, 3]
    assert args[2:] == ("label", "id")


@pytest.fixture
def logged() -> Iterator[list[str]]:
    """Collect formatted loguru messages emitted during the test."""
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    yield messages
    logger.remove(sink_id)


def test_failing_field_is_logged_not_raised(conn: Any, logged: list[str]) -> None:
    """A broken M2M config is logged and leaves the other fields loaded."""
    form = MagicMock()
    m2m: ManyToManyFields = {
        "bad": {"relationship": "missing", "display_field": "label"},
        "tag_ids": {"relationship": "tags", "display_field": "label"},
    }

    load_form_options(form, conn, Post, {}, m2m)

    names = [
        c.args[0] for c in form.input_generator.set_many_to_many_options.mock_calls
    ]
    assert names == ["tag_ids"]
    assert any("many-to-many data for bad" in m for m in logged)
    assert not any("for tag_ids" in m for m in logged)


def test_failing_fk_field_is_logged_not_raised(conn: Any, logged: list[str]) -> None:
    """A bad FK display_field is logged and leaves the other fields loaded."""
    form = MagicMock()
    fk: ForeignKeyOptions = {
        "writer": {
            "query": select(Author),
            "display_field": "nope",
            "value_field": "id",
        },
        "editor": AUTHOR_FK,
    }

    load_form_options(form, conn, Post, fk, {})

    names = [c.args[0] for c in form.input_generator.set_foreign_key_options.mock_calls]
    assert names == ["editor"]
    assert any("foreign key data for writer" in m for m in logged)
    assert not any("for editor" in m for m in logged)


def broken_filter(query: Any) -> Any:
    """M2M filter that always fails, to exercise the option-load error path."""
    msg = f"broken filter for {query}"
    raise ValueError(msg)


def _warning_app(db: str, disable_log: bool) -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function
    from pydantic import BaseModel  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    from streamlit_pydantic_crud.config_types import (  # noqa: PLC0415
        ForeignKeyOptions,
        ManyToManyFields,
    )
    from streamlit_pydantic_crud.create_delete_model import (  # noqa: PLC0415
        CreateRow,
    )
    from streamlit_pydantic_crud.lib import set_logging  # noqa: PLC0415
    from tests.test_form_options import (  # noqa: PLC0415
        Author,
        Post,
        broken_filter,
    )

    class PostForm(BaseModel):
        """Form schema with the FK and M2M fields under test."""

        title: str
        writer: int | None = None
        bad: list[int] = []

    set_logging(disable_log)
    conn = st.connection("sql", url=f"sqlite:///{db}")
    fk: ForeignKeyOptions = {
        "writer": {
            "query": select(Author),
            "display_field": "nope",
            "value_field": "id",
        }
    }
    m2m: ManyToManyFields = {
        "bad": {
            "relationship": "tags",
            "display_field": "label",
            "filter": broken_filter,
        }
    }
    CreateRow(
        conn,
        Post,
        create_schema=PostForm,
        foreign_key_options=fk,
        many_to_many_fields=m2m,
    )
    st.write("RENDERED")


@pytest.fixture
def form_db(tmp_path: Path) -> Iterator[str]:
    """SQLite file with one author and post 1; re-enables logging afterwards."""
    path = tmp_path / "options.db"
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Author(id=1, name="A1"))
        s.add(Post(id=1, title="p", author_id=1))
        s.commit()
    eng.dispose()
    yield str(path)
    logger.enable("streamlit_pydantic_crud")


@pytest.mark.parametrize("disable_log", [False, True])
def test_option_load_failure_shows_warning_per_field(
    form_db: str, logged: list[str], disable_log: bool
) -> None:
    """Each failing field shows a warning, also with logging disabled."""
    kwargs = {"db": form_db, "disable_log": disable_log}
    at = AppTest.from_function(_warning_app, kwargs=kwargs)

    for _ in range(2):
        at.run()
        assert not at.exception
        assert "RENDERED" in [m.value for m in at.markdown]
        assert sorted(w.value for w in at.warning) == [
            "Could not load foreign key options for 'writer'.",
            "Could not load many-to-many options for 'bad'.",
        ]

    failures = [m for m in logged if m.startswith("Failed to load")]
    assert len(failures) == (0 if disable_log else 4)
