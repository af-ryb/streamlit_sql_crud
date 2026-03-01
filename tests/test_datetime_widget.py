from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from streamlit_pydantic_crud.pydantic_utils import (
    PydanticInputGenerator,
    PydanticSQLAlchemyConverter,
)


class TestDatetimeTypeDetection:
    """Tests for datetime type detection in get_streamlit_input_type()."""

    def test_datetime_returns_datetime_input(self) -> None:
        """datetime type maps to 'datetime_input'."""
        field_info = {"inner_type": datetime, "annotation": datetime}
        result = PydanticSQLAlchemyConverter.get_streamlit_input_type(field_info)
        assert result == "datetime_input"

    def test_date_still_returns_date_input(self) -> None:
        """date type still maps to 'date_input' (not affected by datetime addition)."""
        field_info = {"inner_type": date, "annotation": date}
        result = PydanticSQLAlchemyConverter.get_streamlit_input_type(field_info)
        assert result == "date_input"


class TestRenderDatetimeInputWidget:
    """Tests for PydanticInputGenerator._render_datetime_input_widget()."""

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_basic_rendering(self, mock_st: MagicMock) -> None:
        """Renders st.datetime_input with value and key."""
        dt_value = datetime(2025, 6, 15, 14, 30)
        mock_st.datetime_input.return_value = dt_value
        result = PydanticInputGenerator._render_datetime_input_widget(
            label="Event Time",
            widget_kwargs={},
            existing_value=dt_value,
            key="test_key",
        )
        mock_st.datetime_input.assert_called_once_with(
            "Event Time",
            value=dt_value,
            key="test_key",
        )
        assert result == dt_value

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_none_value(self, mock_st: MagicMock) -> None:
        """Renders with None value (empty datetime picker)."""
        mock_st.datetime_input.return_value = None
        result = PydanticInputGenerator._render_datetime_input_widget(
            label="Event Time",
            widget_kwargs={},
            existing_value=None,
            key="test_key",
        )
        mock_st.datetime_input.assert_called_once_with(
            "Event Time",
            value=None,
            key="test_key",
        )
        assert result is None

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_extra_kwargs_passed_through(self, mock_st: MagicMock) -> None:
        """Extra kwargs like min_value, max_value, step are forwarded."""
        dt_value = datetime(2025, 6, 15, 14, 30)
        step = timedelta(minutes=30)
        min_val = datetime(2025, 1, 1)
        max_val = datetime(2025, 12, 31, 23, 59)
        mock_st.datetime_input.return_value = dt_value

        PydanticInputGenerator._render_datetime_input_widget(
            label="Event Time",
            widget_kwargs={
                "min_value": min_val,
                "max_value": max_val,
                "step": step,
            },
            existing_value=dt_value,
            key="test_key",
        )
        mock_st.datetime_input.assert_called_once_with(
            "Event Time",
            value=dt_value,
            key="test_key",
            min_value=min_val,
            max_value=max_val,
            step=step,
        )
