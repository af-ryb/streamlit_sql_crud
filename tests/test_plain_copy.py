"""Copying a row through the plain (no-schema) create form inserts a new row.

Regression: only the Pydantic form dropped the copied primary key, so a plain
copy tried to insert the source row's PK again.
"""

import os
import sqlite3
from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest


def test_plain_copy_creates_a_new_row(
    run_app: Callable[[str], AppTest], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRUD_TEST_MODE", "copy")
    at = run_app("plain_forms_app.py")
    next(b for b in at.button if b.label == "Save").click().run()

    assert not at.exception
    assert "RESULT=True|Created successfully first" in [m.value for m in at.markdown]
    with sqlite3.connect(os.environ["CRUD_TEST_DB"]) as con:
        rows = con.execute(
            "SELECT id, title, note, count FROM item ORDER BY id"
        ).fetchall()
    assert rows == [
        (1, "first", "n1", 5),
        (2, "second", None, 8),
        (3, "first", "n1", 5),
    ]
