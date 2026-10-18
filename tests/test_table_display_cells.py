"""Table cells of enum-array and JSON columns render as readable text.

PostgreSQL enum arrays arrive as lists of Enum members (or a PG array literal);
the table must show the member values, not `DepartmentType.ENGINEERING`.
"""

import enum

import pandas as pd
from sqlalchemy import Column, Enum, MetaData, Table
from sqlalchemy.dialects.postgresql import ARRAY

from streamlit_pydantic_crud.helpers.display import convert_arrow


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
