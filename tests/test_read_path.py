"""Pin today's SqlUi table output for the consumer's read shapes.

Task 3 rewrites the read path and must keep these green unchanged; asserts
noted "flipped in Task 4" record a plain-vs-schema difference Task 4 removes.
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
from streamlit.testing.v1 import AppTest

from tests._apps.read_path_models import (
    ID_ALPHA,
    ID_BRAVO,
    ID_CHARLIE,
    ID_DELTA,
    META_ALPHA,
)

APP = str(Path(__file__).parent / "_apps" / "read_path_app.py")
DF_KEY = "rp_df_sql_ui_0"
"""Rows in PK order: the read query's ORDER BY is overridden by paging."""
PK_ORDER = [ID_BRAVO, ID_CHARLIE, ID_ALPHA, ID_DELTA]
NAMES = ["bravo", "charlie", "alpha", "delta"]
META_TEXT = [
    None,
    json.dumps({"k": 3}, indent=2),
    json.dumps(META_ALPHA, indent=2),
    json.dumps([1, 2], indent=2),
]
PRICE_TEXT = ["3.00", "7.25", "12.50", "0.10"]
ITEM_COLS = ["id", "name", "template_id", "price", "meta", "tags"]


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


def display_text(at: AppTest) -> dict[str, list[str]]:
    """Cell texts the Styler sends to the browser, per column.

    Exists only while rendering goes through a Styler: flipped in Task 4.
    """
    raw = at.dataframe(key=DF_KEY).proto.arrow_data.styler.display_values
    return pa.ipc.open_stream(io.BytesIO(raw)).read_all().to_pydict()


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
    """flipped in Task 4: plain Numeric is float64, schema mode keeps Decimal."""
    assert df["price"].dtype == "float64"
    assert df["price"].tolist() == [3.0, 7.25, 12.5, 0.1]
    """flipped in Task 4: plain ARRAY is a comma string ([] → ""), not a list."""
    assert df["tags"].tolist() == ["", None, "hot, new", "sale"]

    text = display_text(at)
    assert text["price"] == PRICE_TEXT
    assert text["tags"] == ["", "None", "hot, new", "sale"]
    assert text["meta"][0] == "None"


def test_schema_mode_renders_schema_columns(run: Callable[..., AppTest]) -> None:
    at = run("schema")
    df = table(at)

    assert list(df.columns) == ITEM_COLS
    assert column_order(at) == ITEM_COLS
    assert df["id"].tolist() == PK_ORDER
    assert df["name"].tolist() == NAMES
    assert df["template_id"].tolist() == [2, 1, 1, 2]
    assert df["meta"].tolist() == META_TEXT
    """flipped in Task 4: schema Numeric stays Decimal (plain mode: float)."""
    assert df["price"].tolist() == [
        Decimal("3.00"),
        Decimal("7.25"),
        Decimal("12.50"),
        Decimal("0.10"),
    ]
    """flipped in Task 4 (same in plain mode): ARRAY is a list of enum values."""
    assert cells(df, "tags") == [[], None, ["hot", "new"], ["sale"]]

    text = display_text(at)
    assert text["price"] == PRICE_TEXT
    """flipped in Task 4: the Styler shows the Python repr of list cells."""
    assert text["tags"] == ["[]", "None", "['hot', 'new']", "['sale']"]


def test_plain_and_schema_agree_except_known_columns(
    run: Callable[..., AppTest],
) -> None:
    plain = table(run("plain"))
    schema = table(run("schema"))

    for col in ("id", "name", "template_id", "meta"):
        assert plain[col].tolist() == schema[col].tolist(), col
    """flipped in Task 4: these two columns differ between the modes today."""
    assert plain["price"].tolist() != schema["price"].tolist()
    assert plain["tags"].tolist() != cells(schema, "tags")


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
    assert display_text(at)["price"] == PRICE_TEXT


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
    """WHERE drops bravo; ORDER BY (category count: delta, alpha, charlie) is
    overridden by the PK order of paging."""
    assert at.session_state["QTTY"] == 3
    assert df["id"].tolist() == [ID_CHARLIE, ID_ALPHA, ID_DELTA]
    assert df["category_names"].tolist() == ["blue, green, red", "blue, red", "green"]
    assert df["app_name"].tolist() == ["Alpha App", "Alpha App", "Beta App"]
    """Rows are reloaded entities for M2M, but query columns win: `platform` is
    the upper-cased label (as in join mode), not the model @property."""
    assert df["platform"].tolist() == ["IOS", "IOS", "ANDROID"]
    assert display_text(at)["price"] == ["7.25", "12.50", "0.10"]


def test_m2m_filter_options_follow_where(run: Callable[..., AppTest]) -> None:
    at = run("m2m")
    assert at.selectbox(key="rp_create_no_dt_filter_Name").options == [
        "alpha",
        "charlie",
        "delta",
    ]
    at.selectbox(key="rp_create_no_dt_filter_App Name").select("Alpha App").run()
    assert not at.exception
    assert table(at)["id"].tolist() == [ID_CHARLIE, ID_ALPHA]


@pytest.mark.parametrize(
    ("mode", "ids"),
    [
        ("plain", PK_ORDER),
        ("schema", PK_ORDER),
        ("join", PK_ORDER),
        ("m2m", [ID_CHARLIE, ID_ALPHA, ID_DELTA]),
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
        ("m2m", [ID_CHARLIE, ID_ALPHA, ID_DELTA]),
    ],
)
def test_delete_targets_selected_pks(
    run: Callable[..., AppTest], mode: str, ids: list[str]
) -> None:
    at = run(mode, select=[0, 2])
    [(name, kwargs)] = click(at, "delete")
    assert name == "DeleteRows"
    assert kwargs["rows_id"] == [ids[0], ids[2]]


def test_copy_plain_passes_display_row(run: Callable[..., AppTest]) -> None:
    at = run("plain", select=[2])
    [(name, kwargs)] = click(at, "add")
    assert name == "CreateRow"
    data = kwargs["initial_data"]
    assert data["id"] == ID_ALPHA
    assert data["name"] == "alpha"
    assert data["template_id"] == 1
    """flipped in Task 4/5: copy gets the display row, not the raw record."""
    assert data["price"] == 12.5
    assert type(data["price"]) is float
    assert data["meta"] == json.dumps(META_ALPHA, indent=2)
    assert data["tags"] == "hot, new"


def test_copy_schema_passes_display_row(run: Callable[..., AppTest]) -> None:
    at = run("schema", select=[2])
    [(name, kwargs)] = click(at, "add")
    assert name == "CreateRow"
    data = kwargs["initial_data"]
    assert data["id"] == ID_ALPHA
    assert data["name"] == "alpha"
    """flipped in Task 4/5: Decimal kept; JSON is text, tags enum values."""
    assert data["price"] == Decimal("12.50")
    assert data["meta"] == json.dumps(META_ALPHA, indent=2)
    assert data["tags"] == ["hot", "new"]


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
