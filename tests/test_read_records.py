"""`table/read.read_records`: one read path returning raw Python records."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, Select, create_engine, func, select
from sqlalchemy.orm import Session

from streamlit_pydantic_crud.config_types import ManyToManyFields
from streamlit_pydantic_crud.table import query
from streamlit_pydantic_crud.table.read import read_records
from tests._apps.read_path_models import (
    ID_ALPHA,
    ID_BRAVO,
    ID_CHARLIE,
    ID_DELTA,
    META_ALPHA,
    Category,
    Item,
    ItemJoinRead,
    ItemM2MRead,
    ItemRead,
    Tag,
    Template,
    seed,
)

M2M: ManyToManyFields = {
    "categories": {"relationship": "categories", "display_field": "name"}
}
ITEM_COLS = ["id", "name", "template_id", "price", "meta", "tags"]


class EngineConn:
    """Duck-typed SessionSource over an engine."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @property
    def session(self) -> Session:
        """A new Session per use."""
        return Session(self.engine)


@pytest.fixture
def conn(tmp_path: Path) -> EngineConn:
    """A seeded read path database."""
    engine = create_engine(f"sqlite:///{tmp_path / 'records.db'}")
    seed(engine)
    return EngineConn(engine)


def paged(read_instance: Any) -> Select[Any]:
    """Select every row of `read_instance` through its CTE, in PK order."""
    cte = query.to_cte(read_instance)
    return select(cte).order_by(cte.c.id)


def join_stmt() -> Select[Any]:
    """Item JOIN Template with the labels the consumer adds."""
    return select(
        Item,
        Template.app_name.label("app_name"),
        func.upper(Template.platform).label("platform"),
    ).join(Template, Item.template_id == Template.id)


def test_plain_records_keep_raw_values(conn: EngineConn) -> None:
    records = read_records(conn, paged(Item), Item)

    assert [list(r) for r in records] == [ITEM_COLS] * 4
    assert [r["id"] for r in records] == [ID_BRAVO, ID_CHARLIE, ID_ALPHA, ID_DELTA]
    alpha = records[2]
    assert alpha["price"] == Decimal("12.50")
    assert type(alpha["price"]) is Decimal
    assert alpha["meta"] == META_ALPHA
    assert alpha["tags"] == [Tag.HOT, Tag.NEW]
    assert records[0]["tags"] == []
    assert records[0]["meta"] is None


def test_schema_records_are_model_dumps(conn: EngineConn) -> None:
    records = read_records(conn, paged(Item), Item, read_schema=ItemRead)

    assert [list(r) for r in records] == [ITEM_COLS] * 4
    alpha = records[2]
    assert alpha == {
        "id": ID_ALPHA,
        "name": "alpha",
        "template_id": 1,
        "price": Decimal("12.50"),
        "meta": META_ALPHA,
        "tags": [Tag.HOT, Tag.NEW],
    }


def test_join_labels_are_record_keys(conn: EngineConn) -> None:
    records = read_records(conn, paged(join_stmt()), Item)

    assert list(records[0]) == [*ITEM_COLS, "app_name", "platform"]
    assert [r["platform"] for r in records] == ["ANDROID", "IOS", "IOS", "ANDROID"]


def test_schema_without_pk_field_still_has_pk(conn: EngineConn) -> None:
    records = read_records(conn, paged(join_stmt()), Item, read_schema=ItemJoinRead)

    assert list(records[0]) == ["app_name", "platform", "name", "price", "id"]
    assert [r["id"] for r in records] == [ID_BRAVO, ID_CHARLIE, ID_ALPHA, ID_DELTA]


def test_m2m_reloads_only_the_filtered_rows(conn: EngineConn) -> None:
    stmt = join_stmt().where(Item.name.in_(["alpha", "delta"]))
    records = read_records(
        conn, paged(stmt), Item, read_schema=ItemM2MRead, many_to_many_fields=M2M
    )

    assert [r["id"] for r in records] == [ID_ALPHA, ID_DELTA]
    assert [r["category_names"] for r in records] == ["blue, red", "green"]
    assert [r["app_name"] for r in records] == ["Alpha App", "Beta App"]


def test_m2m_without_schema_adds_relationships(conn: EngineConn) -> None:
    records = read_records(conn, paged(Item), Item, many_to_many_fields=M2M)

    alpha = records[2]
    assert alpha["id"] == ID_ALPHA
    assert sorted(c.name for c in alpha["categories"]) == ["blue", "red"]
    assert all(isinstance(c, Category) for c in alpha["categories"])


def test_empty_result_is_empty_list(conn: EngineConn) -> None:
    stmt = select(Item).where(Item.name == "nobody")
    assert read_records(conn, paged(stmt), Item, many_to_many_fields=M2M) == []
