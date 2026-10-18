"""Table cells of enum-array and JSON columns render as readable text.

PostgreSQL enum arrays arrive as lists of Enum members (or a PG array literal);
the table must show the member values, not `DepartmentType.ENGINEERING`.
"""

import enum
import json
from collections.abc import Callable

import pandas as pd
import pytest
from sqlalchemy import Column, Enum, MetaData, Table
from sqlalchemy.dialects.postgresql import ARRAY
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.helpers.display import convert_arrow

"""Values seeded in row 1 by `tests/_apps/json_cells_app.py`."""
META = {"mixed": [1, "two", 3.5, None, True]}
ITEMS = [1, "a", {"k": 2}]


class DepartmentType(enum.Enum):
    """Enum whose str() is `DepartmentType.X`, like the example app enum."""

    ENGINEERING = "ENGINEERING"
    MARKETING = "MARKETING"


ARRAY_TABLE = Table(
    "with_enum_array",
    MetaData(),
    Column("categories", ARRAY(Enum(DepartmentType))),
)


def test_enum_array_cells_show_member_values() -> None:
    """Enum members, PG literals and NULL become value lists or None."""
    df = pd.DataFrame(
        {
            "categories": [
                [DepartmentType.ENGINEERING, DepartmentType.MARKETING],
                "{ENGINEERING,MARKETING}",
                None,
            ]
        }
    )

    convert_arrow(ARRAY_TABLE.columns, df)

    assert df["categories"].tolist() == [
        "ENGINEERING, MARKETING",
        "ENGINEERING, MARKETING",
        None,
    ]


@pytest.mark.parametrize("mode", ["schema", "no_schema"])
def test_json_cells_render_as_text(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Mixed-type JSON lists show as indented JSON text in both read modes."""
    monkeypatch.setenv("CRUD_TEST_MODE", mode)
    at = run_app("json_cells_app.py")

    assert not at.exception
    df = at.dataframe[0].value
    assert df["meta"].tolist() == [json.dumps(META, indent=2), None]
    assert df["items"].tolist() == [json.dumps(ITEMS, indent=2), None]
