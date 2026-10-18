"""ReadManyRel resolves the child model and widget-key suffix of a relationship."""

import pytest
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from streamlit_pydantic_crud.dialogs.one_to_many import ReadManyRel


class Base(DeclarativeBase):
    """Declarative base of the parent/child models."""


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


class OtherBase(DeclarativeBase):
    """A separate registry that does not map the child table."""


class Lonely(OtherBase):
    """Model whose registry has no `child` table."""

    __tablename__ = "lonely"

    id: Mapped[int] = mapped_column(primary_key=True)


def test_other_model_is_the_child() -> None:
    assert ReadManyRel(Parent, 1, Parent.children.property).other_model is Child


def test_suffix_key_unchanged() -> None:
    rel = ReadManyRel(Parent, 1, Parent.children.property)

    assert rel.suffix_key == "parent_parent_id_child"


def test_missing_model_raises_clear_error() -> None:
    rel = ReadManyRel(Lonely, 1, Parent.children.property)

    with pytest.raises(ValueError, match="No mapped model for table 'child'"):
        _ = rel.other_model
