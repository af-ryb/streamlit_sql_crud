"""Numeric table cells use the column scale, not Styler's 6 decimals.

pd.read_sql turns Numeric(10, 2) into float64 and the Styler default then
showed 50000.000000.
"""

from decimal import Decimal

import numpy as np
from sqlalchemy import Float, Integer, Numeric, column, select, table

from streamlit_pydantic_crud.sql_ui import format_number, numeric_formatters

CTE = select(
    table(
        "t",
        column("salary", Numeric(10, 2)),
        column("ratio", Float()),
        column("qty", Integer()),
    )
).cte()


def test_formatters_cover_only_numeric_columns_in_df() -> None:
    result = numeric_formatters(CTE, ["salary", "ratio", "qty"])
    assert set(result) == {"salary", "ratio"}
    assert numeric_formatters(CTE, ["qty"]) == {}


def test_scale_is_applied() -> None:
    fmt = numeric_formatters(CTE, ["salary"])["salary"]
    assert callable(fmt)
    assert fmt(np.float64(50000.0)) == "50000.00"
    assert fmt(Decimal("1234.5")) == "1234.50"


def test_float_without_scale_is_shortest_repr() -> None:
    assert format_number(np.float64(3.14159)) == "3.14159"
    assert format_number(2.0) == "2.0"


def test_missing_values_keep_default_text() -> None:
    assert format_number(np.nan, 2) == "nan"
    assert format_number(None, 2) == "None"
