"""Pagination must use a stable ORDER BY so rows do not jump pages (#2).

Without an explicit ORDER BY, OFFSET/LIMIT returns rows in an undefined
order, so the same row can appear on two pages or none.
"""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from streamlit_pydantic_crud import read_cte
from tests.conftest import Department


def test_get_stmt_pag_orders_by_given_column(engine: Engine) -> None:
    """get_stmt_pag sorts by the provided column across pages."""
    with Session(engine) as s:
        s.add_all(Department(id=i, name=f"D{i}") for i in range(1, 6))
        s.commit()

        # The read statement orders id DESC; pagination must override to ASC.
        cte = select(Department).order_by(Department.id.desc()).cte()
        stmt_no_pag = select(cte)
        order_col = cte.c.get("id")

        page1 = read_cte.get_stmt_pag(stmt_no_pag, 2, 1, order_col)
        page2 = read_cte.get_stmt_pag(stmt_no_pag, 2, 2, order_col)
        ids1 = s.execute(page1).scalars().all()
        ids2 = s.execute(page2).scalars().all()

    assert ids1 == [1, 2]
    assert ids2 == [3, 4]


def test_rendered_table_is_id_ordered(run_app) -> None:
    """SqlUi renders rows ordered by id even when inserted out of order."""
    at = run_app()
    ids_line = next(m.value for m in at.markdown if m.value.startswith("IDS="))
    assert ids_line == "IDS=1,2,3,4,5"
