"""SqlUi rejects a create/update/read schema that does not fit the model."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from streamlit_pydantic_crud import SqlUi
from tests.conftest import Employee


class Unknown(BaseModel):
    """Schema whose only field is not a column of Employee."""

    nickname: str


@pytest.mark.parametrize("operation", ["create", "update", "read"])
def test_incompatible_schema_raises(operation: str) -> None:
    kwargs: dict[str, Any] = {f"{operation}_schema": Unknown}
    with pytest.raises(ValueError, match=rf"^{operation.capitalize()} schema Unknown"):
        SqlUi(conn=MagicMock(), model=Employee, **kwargs)
