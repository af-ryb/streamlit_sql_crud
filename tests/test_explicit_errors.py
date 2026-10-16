"""Former asserts used for control flow now raise explicit errors."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
import sqlalchemy as sa

from streamlit_pydantic_crud import input_fields
from streamlit_pydantic_crud.filters import FkOpt
from streamlit_pydantic_crud.input_fields import InputFields
from streamlit_pydantic_crud.many import ReadManyRel


def test_get_input_value_unnamed_column_raises() -> None:
    fields = InputFields.__new__(InputFields)
    col = cast(Any, sa.literal_column("1"))
    col.description = None
    with pytest.raises(ValueError, match="no name"):
        fields.get_input_value(col, None)


def test_other_col_without_pairs_raises() -> None:
    rel = SimpleNamespace(local_remote_pairs=None)
    many = ReadManyRel(cast(Any, object), 1, cast(Any, rel))
    with pytest.raises(ValueError, match="no local/remote"):
        many.other_col  # noqa: B018


def test_input_fk_unexpected_option_type_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A selectbox returning something other than an FkOpt is a TypeError."""
    monkeypatch.setattr(input_fields.st, "selectbox", lambda *_args, **_kwargs: "stray")
    existing = SimpleNamespace(fk={"author_id": [FkOpt(1, "A1")]})
    fields = InputFields(cast(Any, object), "p", {}, cast(Any, existing))

    with pytest.raises(TypeError, match="Expected an FkOpt"):
        fields.input_fk("author_id", 1)
