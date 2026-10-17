"""Copying a row must not prefill NULL columns with "nan" (copy action)."""

import numpy as np
import pandas as pd

from streamlit_pydantic_crud.helpers.values import row_to_python


def test_missing_values_become_none() -> None:
    df = pd.DataFrame(
        {
            "name": ["a", None],
            "amount": [1.5, np.nan],
            "when": [pd.Timestamp("2025-01-01"), pd.NaT],
            "n": pd.array([1, pd.NA], dtype="Int64"),
        }
    )
    assert row_to_python(df.iloc[1]) == {
        "name": None,
        "amount": None,
        "when": None,
        "n": None,
    }


def test_numpy_scalars_become_python() -> None:
    df = pd.DataFrame({"id": [7], "ratio": [0.5], "flag": [True]})
    row = row_to_python(df.iloc[0])
    assert row == {"id": 7, "ratio": 0.5, "flag": True}
    assert type(row["id"]) is int
    assert type(row["ratio"]) is float
    assert type(row["flag"]) is bool


def test_list_cells_are_kept() -> None:
    df = pd.DataFrame({"tags": [["x", "y"]], "arr": [np.array([1, 2])]})
    assert row_to_python(df.iloc[0]) == {"tags": ["x", "y"], "arr": [1, 2]}
