"""Shared FK / many-to-many option loading for Pydantic CRUD forms."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Engine, ForeignKey, Table, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)
from sqlalchemy.pool import StaticPool

from streamlit_pydantic_crud.form_options import (
    foreign_key_column_names,
    load_form_options,
)


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


AUTHOR_FK = {"query": select(Author), "display_field": "name", "value_field": "id"}


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
    fk = {"author_id": AUTHOR_FK}
    row = Post(id=1, title="p", author_id=3)

    load_form_options(form, conn, Post, fk, {}, row=row, no_dt_filters={"name": "A1"})

    form.input_generator.set_foreign_key_options.assert_called_once_with(
        "author_id", [{"id": 1, "name": "A1"}, {"id": 3, "name": "A3"}], "name", "id"
    )


def test_non_fk_field_runs_raw_query(conn: Any) -> None:
    """A configured field that is not an FK column ignores the page filters."""
    form = MagicMock()
    fk = {"writer": AUTHOR_FK}

    load_form_options(form, conn, Post, fk, {}, no_dt_filters={"name": "A1"})

    options = form.input_generator.set_foreign_key_options.call_args.args[1]
    assert [opt["id"] for opt in options] == [1, 2, 3]


def test_many_to_many_options_apply_filter(conn: Any) -> None:
    form = MagicMock()
    m2m = {
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


def test_failing_field_is_logged_not_raised(conn: Any) -> None:
    """A broken config leaves the other fields loaded."""
    form = MagicMock()
    m2m = {
        "bad": {"relationship": "missing", "display_field": "label"},
        "tag_ids": {"relationship": "tags", "display_field": "label"},
    }

    load_form_options(form, conn, Post, {}, m2m)

    names = [
        c.args[0] for c in form.input_generator.set_many_to_many_options.mock_calls
    ]
    assert names == ["tag_ids"]
