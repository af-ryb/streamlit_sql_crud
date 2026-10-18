"""Default column configs: Numeric by scale, Float in full, ARRAY as a list.

Numbers are formatted by ``st.column_config.NumberColumn`` (no Styler): the
Styler default showed 50000.000000 for Numeric(10, 2).
"""

from typing import Any

from sqlalchemy import ARRAY, Float, Integer, Numeric, String, column, select, table
from streamlit.elements.lib.column_types import ColumnConfig

from streamlit_pydantic_crud.helpers.display import column_configs, number_format

CTE = select(
    table(
        "t",
        column("salary", Numeric(10, 2)),
        column("rate", Numeric()),
        column("ratio", Float()),
        column("qty", Integer()),
        column("tags", ARRAY(String())),
        column("name", String()),
    )
).cte()
ALL = ["salary", "rate", "ratio", "qty", "tags", "name"]


def type_config(config: ColumnConfig) -> dict[str, Any]:
    """The set options of a column's type config (unset ones are None)."""
    options: dict[str, Any] = dict(config.get("type_config") or {})
    return {k: v for k, v in options.items() if v is not None}


def test_configs_cover_numeric_and_array_columns_only() -> None:
    assert set(column_configs(CTE, ALL)) == {"salary", "rate", "ratio", "tags"}


def test_configs_only_for_requested_columns() -> None:
    assert set(column_configs(CTE, ["salary", "absent"])) == {"salary"}
    assert column_configs(CTE, ["qty", "name"]) == {}


def test_numeric_format_follows_scale() -> None:
    configs = column_configs(CTE, ALL)
    assert type_config(configs["salary"]) == {"type": "number", "format": "%.2f"}
    assert type_config(configs["rate"]) == {"type": "number", "format": "plain"}
    assert type_config(configs["ratio"]) == {"type": "number", "format": "plain"}


def test_array_is_list_column() -> None:
    assert type_config(column_configs(CTE, ["tags"])["tags"]) == {"type": "list"}


def test_number_format() -> None:
    assert number_format(0) == "%.0f"
    assert number_format(4) == "%.4f"
    assert number_format(None) == "plain"
