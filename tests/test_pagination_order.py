"""Pagination must use a stable ORDER BY so rows do not jump pages (#2).

Without an explicit ORDER BY, OFFSET/LIMIT returns rows in an undefined
order, so the same row can appear on two pages or none. The read query's own
ORDER BY is honored, with the primary key appended as a tiebreaker.
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import CTE, Engine, Select, create_engine, func, select
from sqlalchemy.orm import Session

from streamlit_pydantic_crud.table import query
from tests._apps.read_path_models import (
    ID_ALPHA,
    ID_BRAVO,
    ID_CHARLIE,
    ID_DELTA,
    Item,
    item_category,
    seed,
)
from tests.conftest import Department

"""Correlated scalar subquery, NULL for an item without categories (bravo)."""
MAX_CATEGORY = (
    select(func.max(item_category.c.category_id))
    .where(item_category.c.item_id == Item.id)
    .correlate(Item)
    .scalar_subquery()
)


def paged_ids(
    s: Session, read_instance: Any, limit: int, page: int, pk: str = "id"
) -> list[Any]:
    """Run page `page` of `read_instance` through the SqlUi query pipeline."""
    stmt, _ = paged_stmt(read_instance, limit, page, pk)
    return list(s.execute(stmt).scalars())


def paged_stmt(
    read_instance: Any, limit: int, page: int, pk: str = "id"
) -> tuple[Select[Any], CTE]:
    """Build the paged statement SqlUi runs for `read_instance`, and its CTE."""
    cte = query.to_cte(read_instance)
    order_by = query.paging_order(read_instance, cte, cte.c.get(pk))
    stmt_no_pag = query.get_stmt_no_pag_dt(cte, {})
    return query.get_stmt_pag(stmt_no_pag, limit, page, order_by), cte


@pytest.fixture
def departments(engine: Engine) -> Engine:
    """Departments whose names repeat, inserted out of id order."""
    names = {4: "B", 1: "A", 5: "B", 2: "B", 3: "A"}
    with Session(engine) as s:
        s.add_all(Department(id=i, name=n) for i, n in names.items())
        s.commit()
    return engine


@pytest.fixture
def items(tmp_path: Path) -> Engine:
    """The seeded read path database (items with M2M categories)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'order.db'}")
    seed(engine)
    return engine


def test_user_order_with_pk_tiebreak(departments: Engine) -> None:
    """The statement's name DESC is kept; equal names fall back to id ASC."""
    stmt = select(Department).order_by(Department.name.desc())
    with Session(departments) as s:
        pages = [paged_ids(s, stmt, 2, page) for page in (1, 2, 3)]

    assert pages == [[2, 4], [5, 1], [3]]


def test_correlated_subquery_order_desc_nulls_last(items: Engine) -> None:
    """Consumer shape: ORDER BY subquery DESC NULLS LAST, then the PK."""
    stmt = select(Item).order_by(MAX_CATEGORY.desc().nulls_last(), Item.id)
    with Session(items) as s:
        ids = paged_ids(s, stmt, 3, 1) + paged_ids(s, stmt, 3, 2)

    """alpha and charlie tie on 3 (charlie's id sorts first); bravo is NULL."""
    assert ids == [ID_CHARLIE, ID_ALPHA, ID_DELTA, ID_BRAVO]


def test_subquery_order_is_a_hidden_column(items: Engine) -> None:
    stmt = select(Item).order_by(MAX_CATEGORY.desc().nulls_last(), Item.id)
    paged, cte = paged_stmt(stmt, 50, 1)
    sql = str(paged.compile(compile_kwargs={"literal_binds": True}))

    assert "_stsql_order_0" in cte.c
    assert [c.key for c in query.visible_columns(cte)] == [
        "id",
        "name",
        "template_id",
        "price",
        "meta",
        "tags",
    ]
    assert list(paged.selected_columns.keys()) == [
        c.key for c in query.visible_columns(cte)
    ]
    """Item.id is selected and already ordered by: no hidden copy, no repeat."""
    order_sql = sql.rsplit("ORDER BY", maxsplit=1)[-1]
    assert order_sql.split("LIMIT")[0].strip() == (
        "anon_1._stsql_order_0 DESC NULLS LAST, anon_1.id"
    )
    assert "_stsql_order_1" not in sql
    """The inner ORDER BY is dropped: the outer query orders."""
    assert sql.count("ORDER BY") == 1


def test_hidden_column_is_not_counted_or_filtered(items: Engine) -> None:
    stmt = select(Item).order_by(MAX_CATEGORY.desc().nulls_last())
    cte = query.to_cte(stmt)
    stmt_no_pag = query.get_stmt_no_pag_dt(cte, {"name": "alpha"})
    count = select(func.count()).select_from(stmt_no_pag.subquery())
    with Session(items) as s:
        assert s.execute(count).scalar_one() == 1
        assert "_stsql_order_0" not in list(s.execute(stmt_no_pag).keys())


def test_plain_column_order_reuses_the_selected_column(departments: Engine) -> None:
    """Like `select(AppId).order_by(AppId.app_name)`: no hidden column."""
    stmt = select(Department).order_by(Department.name)
    paged, cte = paged_stmt(stmt, 50, 1)

    assert not any(c.key.startswith(query.ORDER_LABEL_PREFIX) for c in cte.c)
    order_sql = str(paged).rsplit("ORDER BY", maxsplit=1)[-1]
    assert order_sql.startswith(" anon_1.name, anon_1.id")
    with Session(departments) as s:
        assert list(s.execute(paged).scalars()) == [1, 3, 2, 4, 5]


def test_textual_label_order(departments: Engine) -> None:
    stmt = select(Department.id, Department.name.label("dname")).order_by("dname")
    with Session(departments) as s:
        assert paged_ids(s, stmt, 50, 1) == [1, 3, 2, 4, 5]


def test_limited_statement_keeps_its_inner_order(departments: Engine) -> None:
    """A LIMIT needs the inner ORDER BY to pick its rows."""
    stmt = select(Department).order_by(Department.id.desc()).limit(3)
    with Session(departments) as s:
        assert paged_ids(s, stmt, 50, 1) == [5, 4, 3]


@pytest.mark.parametrize("kind", ["model", "cte"])
def test_model_or_cte_read_instance_orders_by_pk(
    departments: Engine, kind: str
) -> None:
    read_instance = Department if kind == "model" else select(Department).cte()
    with Session(departments) as s:
        assert paged_ids(s, read_instance, 2, 1) == [1, 2]
        assert paged_ids(s, read_instance, 2, 2) == [3, 4]


def test_rendered_table_follows_read_order(run_app) -> None:
    """SqlUi renders rows in the read statement's order (id DESC)."""
    at = run_app()
    ids_line = next(m.value for m in at.markdown if m.value.startswith("IDS="))
    assert ids_line == "IDS=5,4,3,2,1"
