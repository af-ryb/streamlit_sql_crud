"""`type[MappedModel]` accepts SQLModel tables and DeclarativeBase models.

The `_typing_*` functions are never called: `ty check` covers them, so a
public parameter typed `type[DeclarativeBase]` again would fail the checks.
"""

from pydantic import BaseModel
from sqlalchemy import select
from streamlit.connections import SQLConnection

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.delete import DeleteRows
from streamlit_pydantic_crud.dialogs.edit import UpdateRow
from streamlit_pydantic_crud.helpers.sa_model import declarative_model, tablename
from tests._apps.sqlmodel_models import Hero, HeroRead
from tests.conftest import Department


class NotMapped(BaseModel):
    """A plain Pydantic model: not a mapped class."""

    name: str


def _typing_sqlmodel(conn: SQLConnection) -> None:
    SqlUi(conn=conn, read_instance=select(Hero), edit_create_model=Hero)
    SqlUi(conn=conn, read_instance=Hero, edit_create_model=Hero, read_schema=HeroRead)
    SqlUi(conn=conn, model=Hero)
    CreateRow(conn, Hero)
    UpdateRow(conn, Hero, 1)
    DeleteRows(conn, Hero, [1], key="d")


def _typing_declarative(conn: SQLConnection) -> None:
    SqlUi(conn=conn, read_instance=select(Department), edit_create_model=Department)
    SqlUi(conn=conn, model=Department)
    CreateRow(conn, Department)


def _typing_rejects_unmapped(conn: SQLConnection) -> None:
    SqlUi(conn=conn, model=NotMapped)  # ty: ignore[invalid-argument-type]


def test_declarative_model_returns_the_class() -> None:
    """The cast is a no-op at runtime; the internals introspect the class."""
    assert declarative_model(Hero) is Hero
    assert tablename(declarative_model(Hero)) == "hero"
    assert declarative_model(Department) is Department
