"""Table cells are normalized once for display, the same in every read mode.

PostgreSQL enum arrays arrive as lists of Enum members (or a PG array literal);
the table must show the member values, not `DepartmentType.ENGINEERING`.
"""

import enum
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import pyarrow as pa
import pytest
from sqlalchemy import JSON, Column, Date, Enum, MetaData, Numeric, String, Table
from sqlalchemy.dialects.postgresql import ARRAY
from streamlit.dataframe_util import convert_pandas_df_to_arrow_bytes
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.helpers.display import display_records

"""Values seeded in row 1 by `tests/_apps/json_cells_app.py`."""
META = {"mixed": [1, "two", 3.5, None, True]}
ITEMS = [1, "a", {"k": 2}]


class DepartmentType(enum.Enum):
    """Enum whose str() is `DepartmentType.X`, like the example app enum."""

    ENGINEERING = "ENGINEERING"
    MARKETING = "MARKETING"


TABLE = Table(
    "display_cells",
    MetaData(),
    Column("kind", Enum(DepartmentType)),
    Column("categories", ARRAY(Enum(DepartmentType))),
    Column("scores", ARRAY(Numeric(5, 1))),
    Column("names", ARRAY(String())),
    Column("meta", JSON()),
    Column("budget", Numeric(10, 2)),
    Column("started", Date()),
    Column("label", String()),
)


def display(**record: Any) -> dict[str, Any]:
    """Display one record against the columns of `TABLE`."""
    [row] = display_records(TABLE.columns, [record])
    return row


def test_enum_column_shows_value() -> None:
    assert display(kind=DepartmentType.MARKETING) == {"kind": "MARKETING"}


def test_enum_array_shows_member_values() -> None:
    row = display(categories=[DepartmentType.ENGINEERING, DepartmentType.MARKETING])
    assert row == {"categories": ["ENGINEERING", "MARKETING"]}


def test_pg_array_literal_is_parsed_into_a_list() -> None:
    assert display(categories="{ENGINEERING,MARKETING}") == {
        "categories": ["ENGINEERING", "MARKETING"]
    }
    assert display(names='{"a,b",c}') == {"names": ["a,b", "c"]}


def test_array_items_keep_their_type() -> None:
    """Numbers in an ARRAY stay numbers (no str())."""
    row = display(scores=[Decimal("1.5"), Decimal("2.0")], names=[])
    assert row == {"scores": [Decimal("1.5"), Decimal("2.0")], "names": []}


def test_json_dict_and_mixed_list_become_text() -> None:
    assert display(meta=META) == {"meta": json.dumps(META, indent=2)}
    assert display(meta=ITEMS) == {"meta": json.dumps(ITEMS, indent=2)}
    assert display(meta="plain") == {"meta": "plain"}


def test_decimal_and_dates_stay_unchanged() -> None:
    row = display(budget=Decimal("50000.00"), started=date(2024, 1, 2))
    assert row == {"budget": Decimal("50000.00"), "started": date(2024, 1, 2)}
    assert type(row["budget"]) is Decimal


def test_none_stays_none_in_every_kind() -> None:
    columns = ("kind", "categories", "meta", "budget", "label", "no_column")
    record = dict.fromkeys(columns)
    assert display(**record) == record


def test_values_without_a_column_are_converted_by_type() -> None:
    """A read_schema @property has no CTE column: Enum → value, list items too;
    other items (ORM objects, dicts) become str(), scalars stay as they are."""
    row = display(
        main=DepartmentType.ENGINEERING,
        kinds=[DepartmentType.MARKETING, "x", 3, None],
        summary="alpha, beta",
        total=Decimal("1.5"),
        nested=[{"k": 1}],
    )
    assert row == {
        "main": "ENGINEERING",
        "kinds": ["MARKETING", "x", 3, None],
        "summary": "alpha, beta",
        "total": Decimal("1.5"),
        "nested": ["{'k': 1}"],
    }


def test_records_are_copies_in_order() -> None:
    records = [{"kind": DepartmentType.ENGINEERING}, {"kind": None}]
    assert display_records(TABLE.columns, records) == [
        {"kind": "ENGINEERING"},
        {"kind": None},
    ]
    assert records[0]["kind"] is DepartmentType.ENGINEERING


def test_mixed_utc_offsets_convert_to_arrow() -> None:
    """psycopg2 gives DST-dependent fixed offsets; no UTC conversion is needed."""
    winter = datetime(2024, 1, 1, 12, tzinfo=timezone(timedelta(hours=1)))
    summer = datetime(2024, 7, 1, 12, tzinfo=timezone(timedelta(hours=2)))
    df = pd.DataFrame(display_records(TABLE.columns, [{"t": winter}, {"t": summer}]))

    table = pa.ipc.open_stream(convert_pandas_df_to_arrow_bytes(df)).read_all()
    values = table.column("t").to_pylist()
    assert [v.astimezone(UTC) for v in values] == [
        winter.astimezone(UTC),
        summer.astimezone(UTC),
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
