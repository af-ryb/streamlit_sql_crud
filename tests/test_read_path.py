"""Pin today's SqlUi table output for the consumer's read shapes.

Both read modes now display the same values: Numeric as Decimal formatted by
scale (column config), ARRAY as lists of enum values (list column).
"""

import io
import json
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pytest
import streamlit as st
from pandas.io.formats.style import Styler
from streamlit.testing.v1 import AppTest

from tests._apps.read_path_models import (
    ID_ALPHA,
    ID_BRAVO,
    ID_CHARLIE,
    ID_DELTA,
    META_ALPHA,
    Tag,
)

APP = str(Path(__file__).parent / "_apps" / "read_path_app.py")
DF_KEY = "rp_df_sql_ui_0"
"""Rows in PK order: the read query has no ORDER BY (m2m mode has one)."""
PK_ORDER = [ID_BRAVO, ID_CHARLIE, ID_ALPHA, ID_DELTA]
"""m2m mode: ORDER BY category count (delta 1, alpha 2, charlie 3), then name."""
M2M_ORDER = [ID_DELTA, ID_ALPHA, ID_CHARLIE]
NAMES = ["bravo", "charlie", "alpha", "delta"]
META_TEXT = [
    None,
    json.dumps({"k": 3}, indent=2),
    json.dumps(META_ALPHA, indent=2),
    json.dumps([1, 2], indent=2),
]
PRICES = [Decimal("3.00"), Decimal("7.25"), Decimal("12.50"), Decimal("0.10")]
TAGS = [[], None, ["hot", "new"], ["sale"]]
"""Default column configs sent for the Numeric(10, 2) price and the tags ARRAY."""
PRICE_CONFIG = {"type_config": {"type": "number", "format": "%.2f"}}
TAGS_CONFIG = {"type_config": {"type": "list"}}
ITEM_COLS = ["id", "name", "template_id", "price", "meta", "tags"]
"""`styled` mode uses the deprecated style params (tests/test_deprecations)."""
STYLED_WARNINGS = pytest.mark.filterwarnings(
    r"ignore:.*removed in 0\.10\.0:DeprecationWarning"
)


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., AppTest]:
    """Return a callable rendering the harness in a mode, optionally selected."""
    monkeypatch.setenv("CRUD_TEST_DB", str(tmp_path / "read_path.db"))
    monkeypatch.setenv("CRUD_TEST_MODE", "")

    def _run(mode: str, select: list[int] | None = None) -> AppTest:
        os.environ["CRUD_TEST_MODE"] = mode
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30)
        if select is not None:
            at.session_state["SELECT"] = select
        at.run()
        assert not at.exception, [e.message for e in at.exception]
        return at

    return _run


def table(at: AppTest) -> pd.DataFrame:
    """Data of the rendered SqlUi dataframe."""
    return at.dataframe(key=DF_KEY).value


def column_config(at: AppTest) -> dict[str, Any]:
    """Column configs sent to the browser, per column (JSON in the proto)."""
    return json.loads(at.dataframe(key=DF_KEY).proto.columns)


def column_order(at: AppTest) -> list[str]:
    """Visible column order sent to the browser; empty means all columns."""
    return list(at.dataframe(key=DF_KEY).proto.column_order)


def cells(df: pd.DataFrame, col: str) -> list[Any]:
    """Column values as plain Python; Arrow list cells become lists."""
    return [
        None if v is None else list(v) if hasattr(v, "tolist") else v for v in df[col]
    ]


def click(at: AppTest, action: str) -> list[tuple[str, dict[str, Any]]]:
    """Click a CRUD action button; return the recorded dialog calls."""
    at.button(key=f"rp_stsql_action_{action}").click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at.session_state["CALLS"]


def test_plain_mode_renders_every_column(run: Callable[..., AppTest]) -> None:
    at = run("plain")
    df = table(at)

    assert list(df.columns) == ITEM_COLS
    assert column_order(at) == []
    assert df["id"].tolist() == PK_ORDER
    assert df["name"].tolist() == NAMES
    assert df["template_id"].tolist() == [2, 1, 1, 2]
    assert df["meta"].tolist() == META_TEXT
    assert df["price"].tolist() == PRICES
    assert cells(df, "tags") == TAGS

    config = column_config(at)
    assert config["price"] == PRICE_CONFIG
    assert config["tags"] == TAGS_CONFIG
    """No Styler without df_style_formatter / style_fn."""
    assert not at.dataframe(key=DF_KEY).proto.arrow_data.styler.uuid


@pytest.mark.parametrize("mode", ["plain", "schema", "join", "m2m"])
def test_default_path_renders_records_without_dataframe(
    run: Callable[..., AppTest], mode: str
) -> None:
    at = run(mode)
    """st.dataframe gets the list of records; `SqlUi.df` is never built."""
    assert at.session_state["DATA_TYPE"] is list
    assert at.session_state["DF_BUILT"] is False


@STYLED_WARNINGS
def test_styled_path_renders_a_styler(run: Callable[..., AppTest]) -> None:
    at = run("styled")
    assert at.session_state["DATA_TYPE"] is Styler
    """The adapter builds its own frame, not the deprecated `SqlUi.df`."""
    assert at.session_state["DF_BUILT"] is False


def test_rows_hold_raw_records(run: Callable[..., AppTest]) -> None:
    at = run("plain")
    rows = at.session_state["ROWS"]

    assert [r["id"] for r in rows] == PK_ORDER
    alpha = rows[2]
    assert list(alpha) == ITEM_COLS
    """Raw values: JSON stays a dict, tags enum members, Decimal kept."""
    assert alpha["meta"] == META_ALPHA
    assert alpha["tags"] == [Tag.HOT, Tag.NEW]
    assert all(type(t) is Tag for t in alpha["tags"])
    assert type(alpha["price"]) is Decimal
    assert rows[0]["meta"] is None


def test_rows_hold_raw_schema_records(run: Callable[..., AppTest]) -> None:
    at = run("m2m")
    rows = at.session_state["ROWS"]
    assert [r["id"] for r in rows] == M2M_ORDER
    assert rows[1]["category_names"] == "blue, red"


def test_column_config_user_wins(run: Callable[..., AppTest]) -> None:
    at = run("configured")
    config = column_config(at)

    """The user's price config replaces the scale default; tags keep theirs."""
    assert config["price"] == {"type_config": {"type": "number", "format": "dollar"}}
    assert config["tags"] == TAGS_CONFIG
    assert config["name"] == {"label": "Item name", "type_config": {"type": "text"}}
    assert table(at)["price"].tolist() == PRICES


def test_schema_mode_renders_schema_columns(run: Callable[..., AppTest]) -> None:
    at = run("schema")
    df = table(at)

    assert list(df.columns) == ITEM_COLS
    assert column_order(at) == ITEM_COLS
    assert df["id"].tolist() == PK_ORDER
    assert df["name"].tolist() == NAMES
    assert df["template_id"].tolist() == [2, 1, 1, 2]
    assert df["meta"].tolist() == META_TEXT
    assert df["price"].tolist() == PRICES
    assert cells(df, "tags") == TAGS

    config = column_config(at)
    assert config["price"] == PRICE_CONFIG
    assert config["tags"] == TAGS_CONFIG


def test_plain_and_schema_agree(run: Callable[..., AppTest]) -> None:
    plain_at = run("plain")
    schema_at = run("schema")
    plain, schema = table(plain_at), table(schema_at)

    for col in ITEM_COLS:
        assert cells(plain, col) == cells(schema, col), col
    assert column_config(plain_at) == column_config(schema_at)


@STYLED_WARNINGS
def test_style_formatter_keeps_styler_and_wins_over_column_format(
    run: Callable[..., AppTest],
) -> None:
    at = run("styled")
    df = table(at)

    assert df["price"].tolist() == PRICES
    config = column_config(at)
    """A NumberColumn format would hide the Styler text: only tags keep theirs."""
    assert "price" not in config
    assert config["tags"] == TAGS_CONFIG
    styler = at.dataframe(key=DF_KEY).proto.arrow_data.styler
    raw = styler.display_values
    text = pa.ipc.open_stream(io.BytesIO(raw)).read_all().to_pydict()
    assert text["price"] == ["$3.00", "$7.25", "$12.50", "$0.10"]
    """A None cell skips its column formatter instead of raising."""
    assert text["meta"][0] == "None"
    assert "font-weight: bold" in styler.styles


def test_join_labels_render_in_schema_order(run: Callable[..., AppTest]) -> None:
    at = run("join")
    df = table(at)

    """The PK is not in the read schema: added to the data, hidden from view."""
    assert list(df.columns) == ["app_name", "platform", "name", "price", "id"]
    assert column_order(at) == ["app_name", "platform", "name", "price"]
    assert df["id"].tolist() == PK_ORDER
    assert df["name"].tolist() == NAMES
    assert df["app_name"].tolist() == ["Beta App", "Alpha App", "Alpha App", "Beta App"]
    """Without M2M the labels come from the query row (upper-cased there)."""
    assert df["platform"].tolist() == ["ANDROID", "IOS", "IOS", "ANDROID"]
    assert df["price"].tolist() == PRICES
    assert column_config(at)["price"] == PRICE_CONFIG


def test_join_label_filter_lists_and_narrows(run: Callable[..., AppTest]) -> None:
    at = run("join")
    app_filter = at.selectbox(key="rp_create_no_dt_filter_App Name")
    assert app_filter.options == ["Alpha App", "Beta App"]

    app_filter.select("Beta App").run()

    assert not at.exception
    assert at.session_state["QTTY"] == 2
    assert table(at)["id"].tolist() == [ID_BRAVO, ID_DELTA]


def test_m2m_property_where_and_order(run: Callable[..., AppTest]) -> None:
    at = run("m2m")
    df = table(at)

    assert list(df.columns) == [
        "category_names",
        "app_name",
        "platform",
        "name",
        "price",
        "id",
    ]
    assert column_order(at) == [
        "category_names",
        "app_name",
        "platform",
        "name",
        "price",
    ]
    """WHERE drops bravo; the ORDER BY (category count) is honored."""
    assert at.session_state["QTTY"] == 3
    assert df["id"].tolist() == M2M_ORDER
    assert df["category_names"].tolist() == ["green", "blue, red", "blue, green, red"]
    assert df["app_name"].tolist() == ["Beta App", "Alpha App", "Alpha App"]
    """Rows are reloaded entities for M2M, but query columns win: `platform` is
    the upper-cased label (as in join mode), not the model @property."""
    assert df["platform"].tolist() == ["ANDROID", "IOS", "IOS"]
    assert df["price"].tolist() == [Decimal("0.10"), Decimal("12.50"), Decimal("7.25")]
    assert column_config(at)["price"] == PRICE_CONFIG


def test_m2m_filter_options_follow_where(run: Callable[..., AppTest]) -> None:
    at = run("m2m")
    assert at.selectbox(key="rp_create_no_dt_filter_Name").options == [
        "alpha",
        "charlie",
        "delta",
    ]
    at.selectbox(key="rp_create_no_dt_filter_App Name").select("Alpha App").run()
    assert not at.exception
    assert table(at)["id"].tolist() == [ID_ALPHA, ID_CHARLIE]


@pytest.mark.parametrize(
    ("mode", "ids"),
    [
        ("plain", PK_ORDER),
        ("schema", PK_ORDER),
        ("join", PK_ORDER),
        ("m2m", M2M_ORDER),
    ],
)
def test_edit_targets_selected_pk(
    run: Callable[..., AppTest], mode: str, ids: list[str]
) -> None:
    at = run(mode, select=[2])
    [(name, kwargs)] = click(at, "edit")
    assert name == "UpdateRow"
    assert kwargs["row_id"] == ids[2]
    assert type(kwargs["row_id"]) is str


@pytest.mark.parametrize(
    ("mode", "ids"),
    [
        ("plain", PK_ORDER),
        ("schema", PK_ORDER),
        ("join", PK_ORDER),
        ("m2m", M2M_ORDER),
    ],
)
def test_delete_targets_selected_pks(
    run: Callable[..., AppTest], mode: str, ids: list[str]
) -> None:
    at = run(mode, select=[0, 2])
    [(name, kwargs)] = click(at, "delete")
    assert name == "DeleteRows"
    assert kwargs["rows_id"] == [ids[0], ids[2]]


@pytest.mark.parametrize("mode", ["plain", "schema"])
def test_copy_passes_raw_record(run: Callable[..., AppTest], mode: str) -> None:
    at = run(mode, select=[2])
    [(name, kwargs)] = click(at, "add")
    assert name == "CreateRow"
    data = kwargs["initial_data"]
    assert data["id"] == ID_ALPHA
    assert data["name"] == "alpha"
    assert data["template_id"] == 1
    """The raw record: JSON stays a dict, Decimal and enum members are kept."""
    assert data["price"] == Decimal("12.50")
    assert type(data["price"]) is Decimal
    assert data["meta"] == META_ALPHA
    assert data["tags"] == [Tag.HOT, Tag.NEW]
    """A copy: the dialog may pop the PK without touching `rows`."""
    assert data is not at.session_state["ROWS"][2]


@pytest.mark.parametrize(
    ("mode", "pos", "expected"),
    [
        (
            "join",
            2,
            {
                "app_name": "Alpha App",
                "platform": "IOS",
                "name": "alpha",
                "price": Decimal("12.50"),
                "id": ID_ALPHA,
            },
        ),
        (
            "m2m",
            1,
            {
                "category_names": "blue, red",
                "app_name": "Alpha App",
                "platform": "IOS",
                "name": "alpha",
                "price": Decimal("12.50"),
                "id": ID_ALPHA,
            },
        ),
    ],
)
def test_copy_join_passes_schema_row(
    run: Callable[..., AppTest], mode: str, pos: int, expected: dict[str, Any]
) -> None:
    at = run(mode, select=[pos])
    [(name, kwargs)] = click(at, "add")
    assert name == "CreateRow"
    """Copy prefill holds the read schema fields, labels included."""
    assert kwargs["initial_data"] == expected
