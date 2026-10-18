"""Former asserts used for control flow now raise explicit errors."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
import sqlalchemy as sa

from streamlit_pydantic_crud.config_types import FkOpt
from streamlit_pydantic_crud.dialogs.one_to_many import ReadManyRel
from streamlit_pydantic_crud.forms import sa_fields
from streamlit_pydantic_crud.forms.sa_fields import InputFields


def test_get_input_value_unlabeled_column_uses_name() -> None:
    """A column without a description falls back to its name (column_label)."""
    fields = InputFields.__new__(InputFields)
    fields.key_prefix = "t"
    col = cast(Any, sa.Column("id", sa.Integer, primary_key=True))
    col.description = None
    assert fields.get_input_value(col, 7) == 7


def test_other_col_without_pairs_raises() -> None:
    rel = SimpleNamespace(local_remote_pairs=None)
    rel_reader = ReadManyRel(cast(Any, object), 1, cast(Any, rel))
    with pytest.raises(ValueError, match="no local/remote"):
        rel_reader.other_col  # noqa: B018


def test_input_fk_unexpected_option_type_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A selectbox returning something other than an FkOpt is a TypeError."""
    monkeypatch.setattr(sa_fields.st, "selectbox", lambda *_args, **_kwargs: "stray")
    existing = SimpleNamespace(fk={"author_id": [FkOpt(1, "A1")]})
    fields = InputFields(cast(Any, object), "p", {}, cast(Any, existing))

    with pytest.raises(TypeError, match="Expected an FkOpt"):
        fields.input_fk("author_id", 1)
