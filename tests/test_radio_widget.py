from unittest.mock import MagicMock, patch

from streamlit_pydantic_crud.pydantic_utils import PydanticInputGenerator


class TestRenderRadioWidget:
    """Tests for PydanticInputGenerator._render_radio_widget()."""

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_basic_options(self, mock_st: MagicMock) -> None:
        """Radio renders with provided options and defaults to index 0."""
        mock_st.radio.return_value = "area"
        result = PydanticInputGenerator._render_radio_widget(
            label="Chart type",
            widget_kwargs={"options": ["area", "line", "bar"]},
            existing_value=None,
            key="test_key",
        )
        mock_st.radio.assert_called_once_with(
            "Chart type",
            options=["area", "line", "bar"],
            index=0,
            key="test_key",
        )
        assert result == "area"

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_existing_value_sets_index(self, mock_st: MagicMock) -> None:
        """Existing value selects the matching option by index."""
        mock_st.radio.return_value = "line"
        PydanticInputGenerator._render_radio_widget(
            label="Chart type",
            widget_kwargs={"options": ["area", "line", "bar"]},
            existing_value="line",
            key="test_key",
        )
        mock_st.radio.assert_called_once_with(
            "Chart type",
            options=["area", "line", "bar"],
            index=1,
            key="test_key",
        )

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_existing_value_not_in_options(self, mock_st: MagicMock) -> None:
        """Unknown existing value falls back to index 0."""
        mock_st.radio.return_value = "area"
        PydanticInputGenerator._render_radio_widget(
            label="Chart type",
            widget_kwargs={"options": ["area", "line"]},
            existing_value="unknown",
            key="test_key",
        )
        mock_st.radio.assert_called_once_with(
            "Chart type",
            options=["area", "line"],
            index=0,
            key="test_key",
        )

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_horizontal_kwarg_passed_through(self, mock_st: MagicMock) -> None:
        """Extra kwargs like horizontal are forwarded to st.radio."""
        mock_st.radio.return_value = "area"
        PydanticInputGenerator._render_radio_widget(
            label="Chart type",
            widget_kwargs={"options": ["area", "line"], "horizontal": True},
            existing_value=None,
            key="test_key",
        )
        mock_st.radio.assert_called_once_with(
            "Chart type",
            options=["area", "line"],
            index=0,
            key="test_key",
            horizontal=True,
        )

    @patch("streamlit_pydantic_crud.pydantic_utils.st")
    def test_empty_options(self, mock_st: MagicMock) -> None:
        """Empty options list renders without error."""
        mock_st.radio.return_value = None
        PydanticInputGenerator._render_radio_widget(
            label="Choice",
            widget_kwargs={},
            existing_value=None,
            key="test_key",
        )
        mock_st.radio.assert_called_once_with(
            "Choice",
            options=[],
            index=0,
            key="test_key",
        )
