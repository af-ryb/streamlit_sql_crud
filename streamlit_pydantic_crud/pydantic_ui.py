from collections.abc import Callable
from typing import (
    Any,
    cast,
)

import streamlit as st
from loguru import logger
from pydantic import BaseModel, ValidationError

from streamlit_pydantic_crud.config_types import (
    ForeignKeyOptions,
    ManyToManyFields,
    OperationType,
)
from streamlit_pydantic_crud.forms.pydantic.generator import PydanticInputGenerator
from streamlit_pydantic_crud.forms.schema_builder import (
    create_pydantic_model_from_json_schema,
)
from streamlit_pydantic_crud.helpers.display import field_label
from streamlit_pydantic_crud.helpers.typing import model_fields
from streamlit_pydantic_crud.state import clear_state_keys


class PydanticUi[T: BaseModel]:
    """Standalone Pydantic-based Streamlit form generator.
    Creates dynamic forms from Pydantic models with automatic validation,
    session state persistence, and flexible widget customization.
    """

    def __init__(
        self,
        schema: type[T],
        key: str,
        session_state_key: str | None = None,
        pk_name: str = "id",
    ) -> None:
        """Initialize PydanticUi.

        Args:
            schema: Pydantic model class to generate form from
            key: Unique key for the form (used for widget keys)
            session_state_key: Key for session state persistence (defaults to key)
            pk_name: Name of the primary-key field in the schema
        """
        self.schema = schema
        self.key = key
        self.session_state_key = session_state_key or key
        self.pk_name = pk_name
        self.missing_required: list[str] = []

        self.input_generator = self._build_input_generator()
        self._init_session_state()

    def _build_input_generator(self) -> PydanticInputGenerator:
        """Build the field-widget generator; subclasses add relation config."""
        return PydanticInputGenerator(
            schema=self.schema, key_prefix=self.key, pk_name=self.pk_name
        )

    @classmethod
    def from_json_schema(
        cls,
        json_schema: dict[str, Any],
        field_options: dict[str, list[str]] | None = None,
        key: str = "form",
        model_name: str = "DynamicModel",
        session_state_key: str | None = None,
    ) -> "PydanticUi":
        """Create PydanticUi from JSON schema with field options.

        This method allows creating a PydanticUi instance directly from a JSON schema
        and field options, eliminating the need to manually create the Pydantic model first.

        Args:
            json_schema: JSON schema dictionary (from model.model_json_schema())
            field_options: Dictionary mapping field names to option lists for widgets
            key: Unique key for the form
            model_name: Name for the dynamically created model
            session_state_key: Key for session state persistence

        Returns:
            PydanticUi instance with dynamically created schema

        Example:
            ```python
            ui = PydanticUi.from_json_schema(
                json_schema=json_schema,
                field_options=field_options,
                key="form"
            )
            ```
        """
        if field_options is None:
            field_options = {}

        dynamic_schema = create_pydantic_model_from_json_schema(
            json_schema=json_schema, field_options=field_options, model_name=model_name
        )

        return cls(
            schema=cast(Any, dynamic_schema),
            key=key,
            session_state_key=session_state_key,
        )

    def _init_session_state(self) -> None:
        """Initialize session state for form data persistence."""
        if self.session_state_key not in st.session_state:
            st.session_state[self.session_state_key] = {}

    def render(self) -> T | None:
        """Render form UI and return validated model instance.

        Returns:
            Validated Pydantic model instance or None if validation fails
        """
        return self._render_form()

    def _has_required_fields(self, form_data: dict[str, Any]) -> bool:
        """Check if all required fields have values.

        Records the labels of empty required fields in ``missing_required``.
        """
        self.missing_required = [
            self._field_label(field_name)
            for field_name, field_info in model_fields(self.schema).items()
            if field_info.is_required() and form_data.get(field_name) in [None, "", []]
        ]
        return not self.missing_required

    def _field_label(self, field_name: str) -> str:
        """Return the widget label of a field: its description or title-case name."""
        description = model_fields(self.schema)[field_name].description
        return field_label(field_name, description)

    def _display_validation_errors(self, error: ValidationError) -> None:
        """Display validation errors in a user-friendly format."""
        st.error("Validation errors:")
        for err in error.errors():
            field_name = " → ".join(str(loc) for loc in err["loc"])
            st.error(f"**{field_name}**: {err['msg']}")

    def get_session_data(self) -> T | None:
        """Get validated data from session state as model instance.

        Returns:
            Validated Pydantic model instance or None if data is invalid
        """
        try:
            session_data = st.session_state.get(self.session_state_key, {})
            if not session_data:
                return None

            return self.schema(**session_data)

        except ValidationError:
            return None
        except Exception:
            logger.exception("Error getting session data")
            return None

    def clear_session_data(self) -> None:
        """Clear session state data for this form."""
        if self.session_state_key in st.session_state:
            del st.session_state[self.session_state_key]

        self._clear_widget_keys()

    def update_session_data(self, data: dict[str, Any] | BaseModel | None) -> None:
        """Update session state with new data.

        Args:
            data: Dictionary or Pydantic model instance to update session with
        """
        if data is None:
            return

        try:
            if isinstance(data, BaseModel):
                data_dict = data.model_dump()
            else:
                data_dict = data

            """Clear existing widget keys first to avoid a Streamlit error."""
            self._clear_widget_keys()

            """Widget keys are re-seeded on the next render: the widgets may
            already be instantiated, so they cannot be set here."""
            st.session_state[self.session_state_key] = data_dict

        except Exception:
            logger.exception("Error updating session data")

    def _clear_widget_keys(self) -> None:
        """Drop every field's widget value so the next render re-seeds it."""
        clear_state_keys(
            f"{self.key}_{field_name}" for field_name in model_fields(self.schema)
        )

    def get_form_data(self) -> dict[str, Any]:
        """Get current form data as dictionary.

        Returns:
            Dictionary of current form field values
        """
        return st.session_state.get(self.session_state_key, {})

    def collect_widget_data(self) -> T | None:
        """Read committed widget values from session state.

        Useful in on_click callbacks where widget values are
        already committed but render() hasn't been called yet.
        """
        data = {}
        for field_name in model_fields(self.schema):
            widget_key = f"{self.key}_{field_name}"
            if widget_key in st.session_state:
                data[field_name] = st.session_state[widget_key]
        try:
            return self.schema(**data)
        except ValidationError:
            return None

    def render_with_submit(
        self,
        submit_label: str = "Submit",
        on_submit: Callable | None = None,
        on_submit_args: tuple = (),
        on_submit_kwargs: dict | None = None,
    ) -> tuple[T | None, bool]:
        """Render form with submit button and return validated data with submit status.

        Args:
            submit_label: Label for the submit button
            on_submit: Optional callback invoked on form submit
                (runs before rerun via form_submit_button on_click)
            on_submit_args: Positional args for on_submit callback
            on_submit_kwargs: Keyword args for on_submit callback

        Returns:
            Tuple of (validated Pydantic model instance or None, submit button pressed status)
        """
        with st.form(key=f"{self.key}_form"):
            model_instance = self.render()

            btn_kwargs: dict[str, Any] = {}
            if on_submit is not None:
                btn_kwargs["on_click"] = on_submit
                btn_kwargs["args"] = on_submit_args
                btn_kwargs["kwargs"] = on_submit_kwargs or {}

            submitted = st.form_submit_button(submit_label, **btn_kwargs)
            if submitted:
                self._warn_missing_required()

            return model_instance, submitted

    def _warn_missing_required(self) -> None:
        """Show a warning listing the required fields left empty."""
        if self.missing_required:
            names = ", ".join(self.missing_required)
            st.warning(f"Please fill in the required fields: {names}")

    def render_with_columns(self, columns: int = 2) -> T | None:
        """Render form fields in columns layout.

        Args:
            columns: Number of columns to use

        Returns:
            Validated Pydantic model instance or None if validation fails
        """
        return self._render_form(columns)

    def _render_form(self, columns: int | None = None) -> T | None:
        """Render the fields (spread over `columns` if given) and validate them."""
        try:
            existing_values = st.session_state.get(self.session_state_key, {})
            containers = st.columns(columns) if columns else None
            form_data = self.input_generator.generate_form_data(
                existing_values, containers
            )
            st.session_state[self.session_state_key] = form_data

            if self._has_required_fields(form_data):
                try:
                    return self.schema(**form_data)
                except ValidationError as e:
                    self._display_validation_errors(e)
            return None

        except Exception as e:
            logger.exception("Error rendering PydanticUi form")
            st.error(f"Form rendering error: {e!s}")
            return None


class PydanticCrudUi[T: BaseModel](PydanticUi[T]):
    """Pydantic UI component with CRUD-specific functionality.

    Extends PydanticUi with foreign key support for SqlUi components.
    """

    def __init__(
        self,
        schema: type[T],
        key: str,
        session_state_key: str | None = None,
        foreign_key_options: ForeignKeyOptions | None = None,
        many_to_many_fields: ManyToManyFields | None = None,
        pk_name: str = "id",
    ) -> None:
        """Initialize PydanticCrudUi for CRUD operations.

        Args:
            schema: Pydantic model class to generate form from
            key: Unique key for the form (used for widget keys)
            session_state_key: Key for session state persistence (defaults to key)
            foreign_key_options: Configuration for foreign key fields
            many_to_many_fields: Configuration for many-to-many fields
            pk_name: Name of the primary-key field in the schema
        """
        """Set before the parent init, which builds the generator from them."""
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        super().__init__(
            schema=schema,
            key=key,
            session_state_key=session_state_key,
            pk_name=pk_name,
        )

    def _build_input_generator(self) -> PydanticInputGenerator:
        """Build the generator with FK/M2M support, in create mode until an
        operation calls ``set_operation_type``."""
        return PydanticInputGenerator(
            schema=self.schema,
            key_prefix=self.key,
            foreign_key_options=self.foreign_key_options,
            many_to_many_fields=self.many_to_many_fields,
            operation_type="create",
            pk_name=self.pk_name,
        )

    def set_operation_type(self, operation_type: OperationType) -> None:
        """Update the operation type for the input generator.

        Args:
            operation_type: 'create' or 'update'
        """
        self.input_generator.operation_type = operation_type
