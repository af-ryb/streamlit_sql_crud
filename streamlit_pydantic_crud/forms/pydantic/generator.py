"""Generate Streamlit form inputs for a Pydantic schema.

`PydanticInputGenerator` routes each field to a renderer in `widgets` and
collects the values into form data ready for schema validation.
"""

import json
from collections.abc import Sequence
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from loguru import logger
from pydantic import BaseModel
from streamlit.delta_generator import DeltaGenerator

from streamlit_pydantic_crud.config_types import (
    ForeignKeyOptions,
    ManyToManyFields,
    OperationType,
)
from streamlit_pydantic_crud.forms.pydantic import widgets
from streamlit_pydantic_crud.forms.pydantic.field_info import (
    get_pydantic_field_info,
    get_streamlit_input_type,
    is_optional_field,
)
from streamlit_pydantic_crud.forms.pydantic.option_resolve import (
    is_float_number_kwargs,
)
from streamlit_pydantic_crud.helpers.display import field_label
from streamlit_pydantic_crud.helpers.typing import (
    is_enum_annotation,
    is_enum_list_annotation,
    is_list_annotation,
    model_fields,
)


class PydanticInputGenerator:
    """Generates Streamlit inputs based on Pydantic schema"""

    def __init__(
        self,
        schema: type[BaseModel],
        key_prefix: str = "",
        foreign_key_options: ForeignKeyOptions | None = None,
        many_to_many_fields: ManyToManyFields | None = None,
        operation_type: OperationType = "create",
        pk_name: str = "id",
    ) -> None:
        self.schema = schema
        self.key_prefix = key_prefix
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        self.operation_type = operation_type
        self.pk_name = pk_name
        self.field_info = get_pydantic_field_info(schema)

        """Preloaded relation options (no database connection needed)."""
        self.foreign_key_data = {}
        self.many_to_many_data = {}

    def set_foreign_key_options(
        self,
        field_name: str,
        options: list,
        display_field: str | None = None,
        value_field: str | None = None,
    ) -> None:
        """Set foreign key options for a field with preloaded data.

        Args:
            field_name: Name of the foreign key field
            options: List of option values or dict objects
            display_field: Field name to use for display (if options are dicts)
            value_field: Field name to use for values (if options are dicts)
        """
        if isinstance(options, list) and options and isinstance(options[0], dict):
            if not display_field or not value_field:
                msg = "display_field and value_field required when options are dicts"
                raise ValueError(msg)

            option_values = [item[value_field] for item in options]
            option_map = {item[value_field]: item[display_field] for item in options}

            self.foreign_key_data[field_name] = {
                "options": option_values,
                "display_map": option_map,
            }
        else:
            self.foreign_key_data[field_name] = {
                "options": options,
                "display_map": None,
            }

    def set_many_to_many_options(
        self, field_name: str, options: list, display_field: str, pk_name: str = "id"
    ) -> None:
        """Set many-to-many options for a field with preloaded data."""
        self.many_to_many_data[field_name] = {
            "options": options,
            "display_field": display_field,
            "pk_name": pk_name,
        }

    def generate_form_data(
        self,
        existing_values: dict[str, Any] | None = None,
        containers: Sequence[DeltaGenerator] | None = None,
    ) -> dict[str, Any]:
        """Generate form data dictionary for validation

        Args:
            existing_values: Dictionary of existing values for update operations
            containers: Containers (e.g. ``st.columns``) the fields are spread
                over in turn; None renders them in the current container

        Returns:
            Dictionary of form field values
        """
        form_data = {}
        existing_values = existing_values or {}

        rendered = 0
        for field_name, field_info in self.field_info.items():
            key = f"{self.key_prefix}_{field_name}" if self.key_prefix else field_name
            existing_value = existing_values.get(field_name)

            """Create forms skip the primary key."""
            if field_name == self.pk_name and existing_value is None:
                continue

            container: AbstractContextManager[Any] = (
                containers[rendered % len(containers)] if containers else nullcontext()
            )
            rendered += 1
            with container:
                field_value = self.render_field(
                    field_name,
                    field_info=field_info,
                    annotation=field_info.get("annotation"),
                    existing_value=existing_value,
                    key=key,
                )

            if field_value is None and self._is_update_optional(field_info):
                """Updates dump with exclude_unset: send None to clear a value."""
                form_data[field_name] = None
                continue

            if field_value is None or self._is_excluded_empty(field_info, field_value):
                continue

            input_type = get_streamlit_input_type(field_info)
            if input_type == "text_area_json" and isinstance(field_value, str):
                if not field_value:
                    """Empty JSON: None on update, left out on create."""
                    if self.operation_type == "update":
                        form_data[field_name] = None
                    continue
                try:
                    form_data[field_name] = json.loads(field_value)
                except json.JSONDecodeError:
                    """Pass the raw string on so Pydantic reports the error."""
                    form_data[field_name] = field_value
            elif self._is_update_optional(field_info) and (
                field_value == "" or field_value == []
            ):
                form_data[field_name] = None
            else:
                form_data[field_name] = field_value

        return form_data

    def _is_update_optional(self, field_info: dict[str, Any]) -> bool:
        """Return True for an optional field while editing an existing row."""
        return self.operation_type == "update" and is_optional_field(field_info)

    def _is_excluded_empty(self, field_info: dict[str, Any], field_value: Any) -> bool:
        """Return True for an empty optional value a create form leaves out.

        Update forms keep every value so an emptied field can be set to NULL.
        """
        if not is_optional_field(field_info):
            return False
        if self.operation_type == "update":
            return False
        return bool(field_value == "" or field_value == [] or field_value is None)

    def render_field(
        self,
        field_name: str,
        field_info: dict[str, Any],
        annotation: Any,
        existing_value: Any,
        key: str,
    ) -> Any:
        """Render the appropriate Streamlit input for a field based on its type"""
        field_default = field_info.get("default")
        label = field_label(field_name, field_info.get("description"))

        """Custom widgets resolve session/kw/default precedence themselves, so
        pass the raw session value (not pre-filled with the default)."""
        field = model_fields(self.schema)[field_name]
        json_schema_extra = getattr(field, "json_schema_extra", None)
        if json_schema_extra:
            return self._render_custom_field(
                label,
                field_info=field_info,
                existing_value=existing_value,
                key=key,
                json_schema_extra=json_schema_extra,
            )

        """Non-custom paths fall back to the field default when no session value."""
        value = existing_value if existing_value is not None else field_default

        if field_name == self.pk_name:
            return widgets.render_id_field(label, value, key, self.operation_type)

        if field_name in self.foreign_key_options:
            if field_name in self.foreign_key_data:
                return widgets.render_foreign_key_selectbox(
                    label, self.foreign_key_data[field_name], value, key
                )
            return widgets.render_foreign_key_fallback(label, value, key)

        if field_name in self.many_to_many_fields:
            if field_name in self.many_to_many_data:
                return widgets.render_many_to_many_multiselect(
                    label, self.many_to_many_data[field_name], value, key
                )
            logger.warning(
                f"Many-to-many field {field_name} has no loaded data, "
                "falling back to foreign key input"
            )
            logger.warning(f"Field {field_name} not found in foreign_key_options")
            return widgets.render_foreign_key_fallback(label, value, key)

        if is_enum_annotation(annotation):
            return widgets.render_enum_select(label, annotation, value, key)

        if is_enum_list_annotation(annotation):
            return widgets.render_enum_multiselect(label, annotation, value, key)

        if is_list_annotation(annotation):
            return widgets.render_list_multiselect(label, value, key)

        return self._render_basic_input(label, field_info, value, key=key)

    def _render_custom_field(
        self,
        label: str,
        field_info: dict[str, Any],
        existing_value: Any,
        key: str,
        json_schema_extra: dict[str, Any],
    ) -> Any:
        """Render a field configured by ``json_schema_extra`` (widget and kw)."""
        widget_type = json_schema_extra.get("widget")
        widget_kwargs = json_schema_extra.get("kw", {})

        field_default = field_info.get("default")
        """Value widgets fall back to the default; selection widgets resolve
        precedence themselves (session > explicit kw > default)."""
        value = existing_value if existing_value is not None else field_default

        if widget_type == "text_area":
            return widgets.render_text_area(label, widget_kwargs, value, key)
        if widget_type == "text_input":
            return widgets.render_text_input(label, widget_kwargs, value, key)
        if widget_type == "number_input":
            use_int = not is_float_number_kwargs(widget_kwargs)
            return widgets.render_number_input(
                label,
                widget_kwargs,
                value,
                key,
                use_int,
                is_optional_field(field_info),
            )
        if widget_type == "selectbox":
            return widgets.render_selectbox(
                label, widget_kwargs, existing_value, key, field_default
            )
        if widget_type == "multiselect":
            return widgets.render_multiselect(
                label, widget_kwargs, existing_value, key, field_default
            )
        if widget_type == "checkbox":
            return widgets.render_checkbox(label, widget_kwargs, value, key)
        if widget_type == "date_input":
            return widgets.render_date_input(label, widget_kwargs, value, key)
        if widget_type == "datetime_input":
            return widgets.render_datetime_input(label, widget_kwargs, value, key)
        if widget_type == "slider":
            return widgets.render_slider(label, widget_kwargs, value, key)
        if widget_type == "radio":
            return widgets.render_radio(
                label, widget_kwargs, existing_value, key, field_default
            )
        return self._render_basic_input(label, field_info, value, key)

    def _render_basic_input(
        self, label: str, field_info: dict[str, Any], existing_value: Any, key: str
    ) -> Any:
        """Render the widget matching the field's type (or a text area hint)."""
        description = field_info.get("description", "")
        if description and "(text_area)" in description.lower():
            return widgets.render_text_area(
                label,
                {"height": 150, "help": "Enter text content"},
                existing_value,
                key,
            )

        input_type = get_streamlit_input_type(field_info)

        if input_type == "text_input":
            return widgets.render_text_input(label, {}, existing_value, key)
        optional = is_optional_field(field_info)
        if input_type == "number_input_int":
            return widgets.render_number_input(
                label, {"step": 1}, existing_value, key, True, optional
            )
        if input_type == "number_input_float":
            return widgets.render_number_input(
                label, {"step": 0.1}, existing_value, key, False, optional
            )
        if input_type == "checkbox":
            return widgets.render_checkbox(label, {}, existing_value, key)
        if input_type == "date_input":
            return widgets.render_date_input(label, {}, existing_value, key)
        if input_type == "datetime_input":
            return widgets.render_datetime_input(label, {}, existing_value, key)
        if input_type == "number_input_decimal":
            return widgets.render_number_input(
                label, {"step": 0.01}, existing_value, key, False, optional
            )
        if input_type == "text_area_json":
            return widgets.render_json_text_area(
                label,
                {"height": 150, "help": "Enter valid JSON"},
                existing_value=existing_value,
                key=key,
            )
        return widgets.render_text_input(label, {}, existing_value, key)
