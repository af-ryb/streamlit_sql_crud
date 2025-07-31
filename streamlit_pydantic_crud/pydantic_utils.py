import streamlit as st
import json
import re
from typing import Type, Dict, Any, Optional, Union, get_origin, get_args
from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase
from loguru import logger


class PydanticSQLAlchemyConverter:
    """Handles conversion between Pydantic models and SQLAlchemy models"""
    
    @staticmethod
    def validate_schema_compatibility(
        schema: Type[BaseModel], 
        model: Type[DeclarativeBase],
        operation: str
    ) -> bool:
        """Validate that Pydantic schema is compatible with the SQLAlchemy model
        
        Args:
            schema: Pydantic schema class
            model: SQLAlchemy model class
            operation: 'create' or 'update'
            
        Returns:
            bool: True if compatible, False otherwise
        """
        try:
            schema_fields = schema.model_fields
            sqlalchemy_columns = {col.name: col for col in model.__table__.columns}
            
            # Get all relationships in the model
            relationships = {}
            for attr_name in dir(model):
                attr = getattr(model, attr_name)
                if hasattr(attr, 'property') and hasattr(attr.property, 'mapper'):
                    relationships[attr_name] = attr
            
            # Get all properties in the model
            properties = {}
            for attr_name in dir(model):
                attr = getattr(model, attr_name)
                if isinstance(attr, property):
                    properties[attr_name] = attr
            
            # Check if all schema fields exist in the SQLAlchemy model
            for field_name, field_info in schema_fields.items():
                # Check if field exists as a column, relationship, or property
                if (field_name not in sqlalchemy_columns and 
                    field_name not in relationships and 
                    field_name not in properties):
                    table_name = getattr(model, '__tablename__', model.__name__)
                    logger.warning(f"Field '{field_name}' in {schema.__name__} not found in {table_name}")
                    return False
                    
                # Type compatibility check could be added here
                
            # For update operations, ensure the 'id' field is present
            if operation == 'update' and 'id' not in schema_fields:
                logger.warning(f"Update schema {schema.__name__} must include 'id' field")
                return False
            
            # For read operations, no specific requirements
            if operation == 'read':
                pass  # Read schemas can have any subset of fields
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating schema compatibility: {e}")
            return False
    
    @staticmethod
    def pydantic_to_sqlalchemy(
        pydantic_data: BaseModel,
        sqlalchemy_model: Type[DeclarativeBase]
    ) -> DeclarativeBase:
        """Convert Pydantic model instance to SQLAlchemy model instance
        
        Args:
            pydantic_data: Validated Pydantic model instance
            sqlalchemy_model: SQLAlchemy model class
            
        Returns:
            SQLAlchemy model instance
        """
        try:
            # Get the validated data as dict
            data_dict = pydantic_data.model_dump(exclude_unset=True)
            
            # Create the SQLAlchemy instance
            return sqlalchemy_model(**data_dict)
            
        except Exception as e:
            logger.error(f"Error converting Pydantic to SQLAlchemy: {e}")
            raise
    
    @staticmethod
    def sqlalchemy_to_pydantic(
        sqlalchemy_instance: DeclarativeBase,
        pydantic_schema: Type[BaseModel]
    ) -> BaseModel:
        """Convert SQLAlchemy model instance to Pydantic model instance
        
        Args:
            sqlalchemy_instance: SQLAlchemy model instance
            pydantic_schema: Pydantic schema class
            
        Returns:
            Pydantic model instance
        """
        try:
            # Use from_attributes=True configuration to create from SQLAlchemy instance
            return pydantic_schema.model_validate(sqlalchemy_instance)
            
        except Exception as e:
            logger.error(f"Error converting SQLAlchemy to Pydantic: {e}")
            raise
    
    @staticmethod
    def get_pydantic_field_info(schema: Type[BaseModel]) -> Dict[str, Dict[str, Any]]:
        """Extract field information from Pydantic schema for input generation
        
        Args:
            schema: Pydantic schema class
            
        Returns:
            Dict mapping field names to their metadata
        """
        try:
            field_info = {}
            
            for field_name, field in schema.model_fields.items():
                info = {
                    'annotation': field.annotation,
                    'default': field.default,
                    'is_required': field.is_required(),
                    'description': field.description,
                    'constraints': {}
                }
                
                # Extract validation constraints
                if hasattr(field, 'constraints'):
                    for constraint in field.constraints:
                        constraint_type = type(constraint).__name__
                        info['constraints'][constraint_type] = constraint
                
                # Handle Optional types and extract inner types
                if get_origin(field.annotation) is Union:
                    args = get_args(field.annotation)
                    if len(args) == 2 and type(None) in args:
                        # This is Optional[T]
                        info['is_optional'] = True
                        non_none_type = next(arg for arg in args if arg is not type(None))
                        info['inner_type'] = get_origin(non_none_type) or non_none_type
                    else:
                        info['is_optional'] = False
                        info['inner_type'] = get_origin(field.annotation) or field.annotation
                else:
                    info['is_optional'] = not field.is_required()
                    # Extract the origin type (e.g., list from List[str])
                    info['inner_type'] = get_origin(field.annotation) or field.annotation
                
                field_info[field_name] = info
            
            return field_info
            
        except Exception as e:
            logger.error(f"Error extracting Pydantic field info: {e}")
            return {}

    @staticmethod
    def get_streamlit_input_type(pydantic_field_info: Dict[str, Any]) -> str:
        """Determine the appropriate Streamlit input type for Pydantic field
        
        Args:
            pydantic_field_info: Field information from get_pydantic_field_info
            
        Returns:
            String indicating the Streamlit input type to use
        """
        inner_type = pydantic_field_info.get('inner_type', str)
        annotation = pydantic_field_info.get('annotation', str)
        
        # Check for list types (including typing.List)
        if (inner_type is list or 
            get_origin(annotation) is list or 
            get_origin(inner_type) is list or
            str(annotation).startswith('typing.List') or
            str(inner_type).startswith('typing.List')):
            return 'multiselect'
        
        # Map Python types to Streamlit input types
        if inner_type is str:
            return 'text_input'
        elif inner_type is int:
            return 'number_input_int'
        elif inner_type is float:
            return 'number_input_float'
        elif inner_type is bool:
            return 'checkbox'
        elif inner_type is date:
            return 'date_input'
        elif inner_type is Decimal:
            return 'number_input_decimal'
        elif inner_type is dict:
            return 'text_area_json'
        elif inner_type is list:
            return 'multiselect'
        else:
            return 'text_input'  # Default fallback


class PydanticInputGenerator:
    """Generates Streamlit inputs based on Pydantic schema"""
    
    def __init__(self, schema: Type[BaseModel], key_prefix: str = "", foreign_key_options: dict = None, many_to_many_fields: dict = None, operation_type: str = "create"):
        self.schema = schema
        self.key_prefix = key_prefix
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        self.operation_type = operation_type  # 'create' or 'update'
        self.field_info = PydanticSQLAlchemyConverter.get_pydantic_field_info(schema)
        
        # logger.debug(f"PydanticInputGenerator initialized with schema: {schema.__name__}, operation_type: {operation_type}")
        # logger.debug(f"Many-to-many fields configured: {list(self.many_to_many_fields.keys())}")
        
        # For foreign key fields with preloaded options (no database connection needed)
        self.foreign_key_data = {}
        self.many_to_many_data = {}

    def _is_empty_value_for_optional_field(self, field_name: str, field_value: Any) -> bool:
        """Check if a field value should be considered empty for optional fields.
        
        For create operations: empty values are excluded from form data
        For update operations: empty values are converted to None and included in form data
        
        Args:
            field_name: Name of the field
            field_value: Value to check
            
        Returns:
            True if the value should be excluded from form data (create operations only)
        """
        field_info = self.field_info.get(field_name, {})
        is_optional = field_info.get('is_optional', False) or not field_info.get('is_required', True)
        
        # Only filter empty values for optional fields
        if not is_optional:
            return False
        
        # For update operations, we want to include empty values as None
        # so they can be explicitly set to null in the database
        if self.operation_type == "update":
            return False  # Never exclude values in update operations
        
        # For create operations, exclude empty values (original behavior)
        if field_value == "":
            return True
        elif field_value == []:
            return True
        elif field_value is None:
            return True
        
        return False

    @logger.catch()
    def generate_form_data(self, existing_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate form data dictionary for validation
        
        Args:
            existing_values: Dictionary of existing values for update operations
            
        Returns:
            Dictionary of form field values
        """
        
        form_data = {}
        existing_values = existing_values or {}
        
        for field_name, field_info in self.field_info.items():
            key = f"{self.key_prefix}_{field_name}" if self.key_prefix else field_name
            existing_value = existing_values.get(field_name)
            
            # Skip primary key fields to create operations
            if field_name == 'id' and existing_value is None:
                continue
            
            # logger.debug(f"Processing field: {field_name}, is_m2m: {field_name in self.many_to_many_fields}")
            
            # Get field annotation for better type detection
            annotation = field_info.get('annotation')
            
            # Use our custom implementation for all field types
            field_value = self._render_field_input(field_name,
                                                   field_info=field_info,
                                                   annotation=annotation,
                                                   existing_value=existing_value,
                                                   key=key
                                                   )
            
            # Handle field inclusion logic based on operation type
            should_exclude = self._is_empty_value_for_optional_field(field_name, field_value)
            
            if field_value is not None and not should_exclude:
                # For JSON text areas, attempt to parse the string back into a dict
                input_type = PydanticSQLAlchemyConverter.get_streamlit_input_type(field_info)
                if input_type == 'text_area_json' and isinstance(field_value, str):
                    try:
                        # Do not parse empty strings
                        if field_value:
                            form_data[field_name] = json.loads(field_value)
                        else:
                            # Handle case where field is optional - skip empty values for create, convert to None for update
                            if self.operation_type == "update":
                                form_data[field_name] = None
                            continue
                    except json.JSONDecodeError:
                        # If parsing fails, pass the original string to Pydantic for validation
                        form_data[field_name] = field_value
                else:
                    # For update operations, check if we need to convert empty values to None
                    if self.operation_type == "update":
                        field_info_local = self.field_info.get(field_name, {})
                        is_optional = field_info_local.get('is_optional', False) or not field_info_local.get('is_required', True)
                        if is_optional and (field_value == "" or field_value == []):
                            form_data[field_name] = None
                        else:
                            form_data[field_name] = field_value
                    else:
                        form_data[field_name] = field_value
            elif self.operation_type == "update" and field_value is not None:
                # This branch handles cases where should_exclude is True but we're in update mode
                # (This shouldn't happen anymore since we changed _is_empty_value_for_optional_field)
                field_info_local = self.field_info.get(field_name, {})
                is_optional = field_info_local.get('is_optional', False) or not field_info_local.get('is_required', True)
                if is_optional and (field_value == "" or field_value == []):
                    form_data[field_name] = None
                elif not is_optional:
                    # Include non-optional fields even if empty for validation
                    form_data[field_name] = field_value
        
        return form_data

    def _render_field_input(self, field_name: str, field_info: Dict[str, Any], annotation: Any, existing_value: Any,
                            key: str) -> Any:
        """Render the appropriate Streamlit input for a field based on its type"""
        
        # Use default value if no existing value is provided
        if existing_value is None:
            default_value = field_info.get('default')
            # Check if default is not PydanticUndefined
            if default_value is not None and repr(default_value) != 'PydanticUndefined':
                existing_value = default_value
        
        # Ensure label is always a string
        description = field_info.get('description')
        if description is None or description == '':
            label = field_name.replace('_', ' ').title()
        else:
            label = str(description)
        
        # Check for json_schema_extra customization first
        if hasattr(self.schema, 'model_fields') and field_name in self.schema.model_fields:
            field = self.schema.model_fields[field_name]
            json_schema_extra = getattr(field, 'json_schema_extra', None)
            if json_schema_extra:
                return self._render_custom_field(label,
                                                 field_name=field_name,
                                                 field_info=field_info,
                                                 annotation=annotation,
                                                 existing_value=existing_value,
                                                 key=key,
                                                 json_schema_extra=json_schema_extra
                                                 )
        
        # Handle ID field specially
        if field_name == 'id':
            return self._render_id_field(label, existing_value, key)
        
        # Check for custom foreign key fields first
        elif field_name in self.foreign_key_options:
            # Check if we have preloaded data for this field
            if field_name in self.foreign_key_data:
                return self._render_foreign_key_selectbox(label, field_name, existing_value, key)
            else:
                return self._render_foreign_key_input(label, field_name, existing_value, key=key)
        
        # Check for many-to-many fields
        elif field_name in self.many_to_many_fields:
            # logger.debug(f"Field {field_name} is a many-to-many field. Data loaded: {field_name in self.many_to_many_data}")
            if field_name in self.many_to_many_data:
                return self._render_many_to_many_multiselect(label, field_name, existing_value, key)
            else:
                logger.warning(f"Many-to-many field {field_name} has no loaded data, falling back to foreign key input")
                return self._render_foreign_key_input(label, field_name, existing_value, key=key)

        # Check for enum types - simplified detection based on streamlit-pydantic approach
        elif self._is_enum_field(annotation):
            return self._render_enum_input(label, annotation, existing_value, key=key)
        
        # Check for a list of enums
        elif self._is_enum_list_field(annotation):
            return self._render_enum_list_input(label, annotation, existing_value, key=key)
            
        # Check for regular lists
        elif self._is_list_field(annotation):
            return self._render_list_input(label, annotation, existing_value, key=key)
            
        # Fall back to basic type detection
        else:
            return self._render_basic_input(label, field_info, existing_value, key=key)
    
    def _is_enum_field(self, annotation: Any) -> bool:
        """Check if field is a single enum"""
        # Direct enum check
        if annotation and hasattr(annotation, '__members__'):
            return True
            
        # Check Optional[Enum] (Union with None)
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            for arg in args:
                if arg is not type(None) and hasattr(arg, '__members__'):
                    return True
        
        return False
    
    def _is_enum_list_field(self, annotation: Any) -> bool:
        """Check if field is a list of enums"""
        origin = get_origin(annotation)
        args = get_args(annotation)
        
        # Check List[Enum]
        if origin is list and args and hasattr(args[0], '__members__'):
            return True
            
        # Check Optional[List[Enum]]
        if origin is Union and args:
            for arg in args:
                if arg is not type(None):
                    inner_origin = get_origin(arg)
                    inner_args = get_args(arg)
                    if inner_origin is list and inner_args and hasattr(inner_args[0], '__members__'):
                        return True
        return False
    
    @staticmethod
    def _is_list_field(annotation: Any) -> bool:
        """Check if specified field is a regular list"""
        origin = get_origin(annotation)
        
        # Check List[T]
        if origin is list:
            return True
            
        # Check Optional[List[T]]
        if origin is Union:
            args = get_args(annotation)
            for arg in args:
                if arg is not type(None) and get_origin(arg) is list:
                    return True
        return False

    @staticmethod
    def _render_enum_input(label: str, annotation: Any, existing_value: Any, key: str) -> Any:
        """Render selectbox for single enum"""
        # Extract the actual enum type from Optional[Enum] if needed
        enum_type = annotation
        if get_origin(annotation) is Union:
            args = get_args(annotation)
            for arg in args:
                if arg is not type(None) and hasattr(arg, '__members__'):
                    enum_type = arg
                    break
        
        enum_values = [member.value for member in enum_type.__members__.values()]
        current_index = None
        if existing_value and hasattr(existing_value, 'value'):
            try:
                current_index = enum_values.index(existing_value.value)
            except ValueError:
                pass
        elif existing_value in enum_values:
            try:
                current_index = enum_values.index(existing_value)
            except ValueError:
                pass
                
        return st.selectbox(label, enum_values, index=current_index, key=key)
    
    def _render_foreign_key_input(self, label: str, field_name: str, existing_value: Any, key: str) -> Any:
        """Render selectbox for foreign key fields using custom configuration"""
        if field_name not in self.foreign_key_options:
            logger.warning(f"Field {field_name} not found in foreign_key_options")
            return st.text_input(
                label,
                value=str(existing_value) if existing_value is not None else "",
                key=key,
                help="Configuration not available"
            )
        
        fk_config = self.foreign_key_options[field_name]
        query = fk_config['query']
        display_field = fk_config['display_field']
        value_field = fk_config['value_field']
        
        # Execute query to get options
        if hasattr(self, 'conn') and self.conn:
            with self.conn.session as session:
                rows = session.execute(query).scalars().all()
                
                # Build options
                options = []
                option_map = {}
                for row in rows:
                    value = getattr(row, value_field)
                    display = getattr(row, display_field)
                    options.append(value)
                    option_map[value] = display
                
                # Find current index
                current_index = None
                if existing_value in options:
                    current_index = options.index(existing_value)
                
                # Render selectbox with format_func
                return st.selectbox(
                    label,
                    options=options,
                    index=current_index,
                    format_func=lambda x: option_map.get(x, str(x)),
                    key=key,
                    help=f"Select from {len(options)} available options"
                )
        else:
            # Fallback to text input if no connection available
            return st.text_input(
                label,
                value=str(existing_value) if existing_value is not None else "",
                key=key,
                help="Database connection not available for foreign key options"
            )
    
    def _render_id_field(self, label: str, existing_value: Any, key: str) -> Any:
        """Render ID field specially based on operation type"""
        # Determine operation type based on key prefix and existing value
        is_update = (self.key_prefix == "update" or 
                     (existing_value is not None and existing_value != ""))
        
        if is_update:
            # Update operation: show ID as disabled text input (visible but not editable)
            return st.text_input(
                label,
                value=str(existing_value),
                disabled=True,
                key=key,
                help="ID field (read-only)"
            )
        else:
            # Create operation: don't show ID field at all
            # Return None so it doesn't get included in form data
            return None
    
    def _render_enum_list_input(self, label: str, annotation: Any, existing_value: Any, key: str) -> Any:
        """Render multiselect for list of enums"""
        # Extract enum type
        enum_type = self._extract_enum_from_list_annotation(annotation)
        
        if not enum_type:
            return st.multiselect(label, [], key=key, accept_new_options=True)
            
        # Use enum values for the options
        enum_values = [member.value for member in enum_type.__members__.values()]
        
        # Convert existing values to display format
        current_values = []
        if existing_value is not None:
            if isinstance(existing_value, (list, tuple)):
                current_values = [str(item) for item in existing_value]
            elif isinstance(existing_value, str):
                # Handle PostgreSQL array format
                current_values = self._parse_array_string(existing_value)
        
        return st.multiselect(
            label, 
            enum_values, 
            default=current_values, 
            key=key,
            help=f"Available options: {', '.join(enum_values)}"
        )
    
    def _extract_enum_from_list_annotation(self, annotation: Any) -> Any:
        """Extract enum type from List[Enum] or Optional[List[Enum]]"""
        origin = get_origin(annotation)
        args = get_args(annotation)
        
        # Check List[Enum]
        if origin is list and args:
            return args[0]
            
        # Check Optional[List[Enum]]
        if origin is Union and args:
            for arg in args:
                if arg is not type(None):
                    inner_origin = get_origin(arg)
                    inner_args = get_args(arg)
                    if inner_origin is list and inner_args:
                        return inner_args[0]
        
        return None

    @staticmethod
    def _parse_array_string(value_str: str) -> list:
        """Parse PostgreSQL array string format"""
        value_str = value_str.strip()
        if value_str.startswith('{') and value_str.endswith('}'):
            value_str = value_str[1:-1]
            
        if value_str:
            # Handle quoted and unquoted values
            parts = re.findall(r'"([^"]*)"|\\b([^,]+)\\b', value_str)
            result = []
            for quoted, unquoted in parts:
                val = quoted if quoted else unquoted
                if val.strip():
                    result.append(val.strip())
            
            # Fallback: simple comma split
            if not result:
                result = [v.strip() for v in value_str.split(',') if v.strip()]
            return result
        return []
    
    def _render_list_input(self, label: str, annotation: Any, existing_value: Any, key: str) -> Any:
        """Render multiselect for regular lists"""
        current_values = []
        if existing_value is not None:
            if isinstance(existing_value, (list, tuple)):
                current_values = [str(item) for item in existing_value]
            elif isinstance(existing_value, str):
                current_values = self._parse_array_string(existing_value)
        
        return st.multiselect(
            label, 
            current_values,  # Start with current values as options
            default=current_values, 
            accept_new_options=True,
            key=key,
            help="Select existing options or type new ones"
        )

    def _render_basic_input(self, label: str, field_info: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render basic input types using dedicated widget handlers"""
        # Check if the field should be rendered as text area based on description
        description = field_info.get('description', '')
        if description and '(text_area)' in description.lower():
            return self._render_text_area_widget(
                label, {"height": 150, "help": "Enter text content"}, existing_value, key
            )
        
        input_type = PydanticSQLAlchemyConverter.get_streamlit_input_type(field_info)
        
        if input_type == 'text_input':
            return self._render_text_input_widget(label, {}, existing_value, key)
        elif input_type == 'number_input_int':
            return self._render_number_input_widget(label, {"step": 1}, existing_value, key, use_int=True)
        elif input_type == 'number_input_float':
            return self._render_number_input_widget(label, {"step": 0.1}, existing_value, key,
                                                    use_int=False)
        elif input_type == 'checkbox':
            return self._render_checkbox_widget(label, {}, existing_value, key)
        elif input_type == 'date_input':
            return self._render_date_input_widget(label, {}, existing_value, key)
        elif input_type == 'number_input_decimal':
            return self._render_number_input_widget(label, {"step": 0.01}, existing_value, key, use_int=False)
        elif input_type == 'text_area_json':
            return self._render_json_text_area_widget(label, {"height": 150, "help": "Enter valid JSON"},
                                                      existing_value=existing_value, key=key)
        else:
            # Fallback to text input
            return self._render_text_input_widget(label, {}, existing_value, key)

    def _render_custom_field(self, label: str, field_name: str, field_info: Dict[str, Any],
                             annotation: Any, existing_value: Any, key: str, json_schema_extra: Dict[str, Any]) -> Any:
        """Render field with custom json_schema_extra configuration using dedicated handlers"""
        
        # Extract custom configuration
        widget_type = json_schema_extra.get('widget', None)
        widget_kwargs = json_schema_extra.get('kw', {})
        layout = json_schema_extra.get('layout', None)  # For future use
        
        # Route to the appropriate widget handler based on widget_type
        if widget_type == 'text_area':
            return self._render_text_area_widget(label, widget_kwargs, existing_value, key)
        elif widget_type == 'text_input':
            return self._render_text_input_widget(label, widget_kwargs, existing_value, key)
        elif widget_type == 'number_input':
            use_int = not self._should_use_float_for_number_input(widget_kwargs)
            return self._render_number_input_widget(label, widget_kwargs, existing_value, key, use_int)
        elif widget_type == 'selectbox':
            return self._render_selectbox_widget(label, widget_kwargs, existing_value, key)
        elif widget_type == 'multiselect':
            return self._render_multiselect_widget(label, widget_kwargs, existing_value, key)
        elif widget_type == 'checkbox':
            return self._render_checkbox_widget(label, widget_kwargs, existing_value, key)
        elif widget_type == 'date_input':
            return self._render_date_input_widget(label, widget_kwargs, existing_value, key)
        elif widget_type == 'slider':
            return self._render_slider_widget(label, widget_kwargs, existing_value, key)
        else:
            # Fallback: use default rendering
            return self._render_basic_input(label, field_info, existing_value, key)
    
    def _render_slider_widget(self, label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render slider widget with proper type handling"""
        min_val = widget_kwargs.get('min_value', 0)
        max_val = widget_kwargs.get('max_value', 100)
        step = widget_kwargs.get('step', 1)
        
        # Determine a target type based on step or other parameters
        use_float = self._should_use_float_for_number_input(widget_kwargs)
        
        # Convert all values to the same type
        try:
            if use_float:
                # Use a float type for all values
                min_val = float(min_val)
                max_val = float(max_val)
                step = float(step)
                if existing_value is not None:
                    default_val = float(existing_value)
                else:
                    default_val = min_val
            else:
                # Use an int type for all values
                min_val = int(float(min_val))  # Convert through float first to handle strings like "1.0"
                max_val = int(float(max_val))
                step = int(float(step))
                if existing_value is not None:
                    default_val = int(float(existing_value))
                else:
                    default_val = min_val
        except (ValueError, TypeError):
            # Fallback to safe defaults
            min_val = 0 if not use_float else 0.0
            max_val = 100 if not use_float else 100.0
            step = 1 if not use_float else 1.0
            default_val = min_val

        # Ensure default_val is within bounds
        default_val = max(min_val, min(max_val, default_val))
        
        return st.slider(
            label,
            min_value=min_val,
            max_value=max_val,
            value=default_val,
            step=step,
            key=key,
            **{k: v for k, v in widget_kwargs.items() if k not in ['min_value', 'max_value', 'step', 'value']}
        )

    @staticmethod
    def _render_text_input_widget(label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render text input widget"""
        default_value = str(existing_value) if existing_value is not None else ""
        return st.text_input(
            label,
            value=default_value,
            key=key,
            **widget_kwargs
        )

    @staticmethod
    def _render_text_area_widget(label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render text area widget"""
        default_value = str(existing_value) if existing_value is not None else ""
        return st.text_area(
            label,
            value=default_value,
            key=key,
            **widget_kwargs
        )

    @staticmethod
    def _render_checkbox_widget(label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render checkbox widget"""
        default_val = bool(existing_value) if existing_value is not None else False
        return st.checkbox(
            label,
            value=default_val,
            key=key,
            **widget_kwargs
        )

    @staticmethod
    def _render_date_input_widget(label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render date input widget"""
        return st.date_input(
            label,
            value=existing_value,
            key=key,
            **widget_kwargs
        )

    @staticmethod
    def _render_selectbox_widget(label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render selectbox widget"""
        options = widget_kwargs.get('options', [])
        index = None
        if existing_value and existing_value in options:
            index = options.index(existing_value)
        return st.selectbox(
            label,
            options=options,
            index=index,
            key=key,
            **{k: v for k, v in widget_kwargs.items() if k != 'options'}
        )

    def _render_number_input_widget(self, label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str,
                                    use_int: bool = False) -> Any:
        """Render a number input widget with proper type handling"""
        min_val = widget_kwargs.get('min_value')
        max_val = widget_kwargs.get('max_value')
        step = widget_kwargs.get('step')

        # Determine type based on use_int parameter or widget kwargs
        if not use_int:
            use_int = not self._should_use_float_for_number_input(widget_kwargs)

        try:
            if use_int:
                # Convert all to int
                if min_val is not None:
                    min_val = int(float(min_val))
                if max_val is not None:
                    max_val = int(float(max_val))
                if step is not None:
                    step = int(float(step))
                else:
                    step = 1
                default_val = int(float(existing_value)) if existing_value is not None else 0
            else:
                # Convert all to float
                if min_val is not None:
                    min_val = float(min_val)
                if max_val is not None:
                    max_val = float(max_val)
                if step is not None:
                    step = float(step)
                else:
                    step = 0.1
                default_val = float(existing_value) if existing_value is not None else 0.0
        except (ValueError, TypeError):
            # Fallback to safe defaults
            if use_int:
                min_val = min_val if min_val is not None else None
                max_val = max_val if max_val is not None else None
                step = 1
                default_val = 0
            else:
                min_val = min_val if min_val is not None else None
                max_val = max_val if max_val is not None else None
                step = 0.1
                default_val = 0.0

        # Ensure default_val is within bounds
        if min_val is not None and max_val is not None:
            default_val = max(min_val, min(max_val, default_val))
        elif min_val is not None:
            default_val = max(min_val, default_val)
        elif max_val is not None:
            default_val = min(max_val, default_val)

        # Update widget_kwargs with consistent types
        updated_kwargs = widget_kwargs.copy()
        if min_val is not None:
            updated_kwargs['min_value'] = min_val
        if max_val is not None:
            updated_kwargs['max_value'] = max_val
        if step is not None:
            updated_kwargs['step'] = step

        return st.number_input(
            label,
            value=default_val,
            key=key,
            **updated_kwargs
        )

    def _render_multiselect_widget(self, label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render multiselect widget"""
        options = widget_kwargs.get('options', [])
        default_vals = []
        if existing_value:
            if isinstance(existing_value, (list, tuple)):
                default_vals = list(existing_value)
            elif isinstance(existing_value, str):
                default_vals = self._parse_array_string(existing_value)
        return st.multiselect(
            label,
            options=options,
            default=default_vals,
            key=key,
            **{k: v for k, v in widget_kwargs.items() if k != 'options'}
        )
    
    @staticmethod
    def _render_json_text_area_widget(label: str, widget_kwargs: Dict[str, Any], existing_value: Any, key: str) -> Any:
        """Render text area widget for JSON input"""
        json_value = ""
        if existing_value is not None:
            try:
                if isinstance(existing_value, (dict, list)):
                    json_value = json.dumps(existing_value, indent=2)
                else:
                    json_value = str(existing_value)
            except Exception as e:
                logger.warning(f"Got exception while render JSON, {e}")
                json_value = str(existing_value)
        return st.text_area(
            label,
            value=json_value,
            key=key,
            **widget_kwargs
        )
    
    @staticmethod
    def _should_use_float_for_number_input(widget_kwargs: Dict[str, Any]) -> bool:
        """Determine if number input should use a float type based on parameters"""
        min_val = widget_kwargs.get('min_value')
        max_val = widget_kwargs.get('max_value')
        step = widget_kwargs.get('step')
        
        return (isinstance(step, float) or isinstance(min_val, float) or 
                isinstance(max_val, float) or (step and '.' in str(step)))
    
    def set_foreign_key_options(self, field_name: str, options: list, display_field: str = None, value_field: str = None):
        """Set foreign key options for a field with preloaded data.
        
        Args:
            field_name: Name of the foreign key field
            options: List of option values or dict objects
            display_field: Field name to use for display (if options are dicts)
            value_field: Field name to use for values (if options are dicts)
        """
        if isinstance(options, list) and options and isinstance(options[0], dict):
            # Options are dict objects - extract display and value mappings
            if not display_field or not value_field:
                raise ValueError("display_field and value_field required when options are dicts")
                
            option_values = [item[value_field] for item in options]
            option_map = {item[value_field]: item[display_field] for item in options}
            
            self.foreign_key_data[field_name] = {
                'options': option_values,
                'display_map': option_map
            }
        else:
            # Options are simple values
            self.foreign_key_data[field_name] = {
                'options': options,
                'display_map': None
            }
    
    def _render_foreign_key_selectbox(self, label: str, field_name: str, existing_value: Any, key: str) -> Any:
        """Render selectbox for foreign key fields using preloaded data."""
        if field_name not in self.foreign_key_data:
            # Fallback to text input if no data available
            return st.text_input(
                label,
                value=str(existing_value) if existing_value is not None else "",
                key=key,
                help="Foreign key options not loaded"
            )
        
        fk_data = self.foreign_key_data[field_name]
        options = fk_data['options']
        display_map = fk_data['display_map']
        
        # Find current index
        current_index = None
        if existing_value in options:
            current_index = options.index(existing_value)
        
        # Render selectbox
        if display_map:
            # Use display mapping
            return st.selectbox(
                label,
                options=options,
                index=current_index,
                format_func=lambda x: display_map.get(x, str(x)),
                key=key,
                help=f"Select from {len(options)} available options"
            )
        else:
            # Use options directly
            return st.selectbox(
                label,
                options=options,
                index=current_index,
                key=key,
                help=f"Select from {len(options)} available options"
            )

    def set_many_to_many_options(self, field_name: str, options: list, display_field: str):
        """Set many-to-many options for a field with preloaded data."""
        self.many_to_many_data[field_name] = {
            'options': options,
            'display_field': display_field,
        }
        # logger.debug(f"Set many-to-many options for field {field_name}: {len(options)} options")

    def _render_many_to_many_multiselect(self, label: str, field_name: str, existing_value: Any, key: str) -> Any:
        """Render multiselect for many-to-many fields using preloaded data."""
        if field_name not in self.many_to_many_data:
            logger.warning(f"Many-to-many field {field_name} not found in loaded data. Available fields: {list(self.many_to_many_data.keys())}")
            return st.multiselect(label, [], key=key, help="Many-to-many options not loaded")

        m2m_data = self.many_to_many_data[field_name]
        options = m2m_data['options']
        display_field = m2m_data['display_field']

        # Create mappings for display and ID retrieval
        id_to_display = {option.id: getattr(option, display_field) for option in options}
        id_to_object = {option.id: option for option in options}

        # Get the currently selected IDs
        current_selection_ids = []
        if existing_value is not None:
            if isinstance(existing_value, list) and existing_value:
                # Check if it's a list of IDs, objects, or names
                first_item = existing_value[0]
                if isinstance(first_item, (int, str)):
                    # Check if these are valid IDs or display names
                    if first_item in id_to_display:
                        # List of IDs from session state
                        current_selection_ids = existing_value
                    else:
                        # List of display names (from copy mode) - need to convert to IDs
                        name_to_id = {v: k for k, v in id_to_display.items()}
                        current_selection_ids = [name_to_id.get(name) for name in existing_value if name in name_to_id]
                        # logger.debug(f"Converted display names to IDs for {field_name}: {existing_value} -> {current_selection_ids}")
                elif hasattr(first_item, 'id'):
                    # List of objects from relationship
                    current_selection_ids = [obj.id for obj in existing_value]
            elif hasattr(existing_value, '__iter__') and not isinstance(existing_value, str):
                # Relationship collection - extract IDs
                current_selection_ids = [obj.id for obj in existing_value if hasattr(obj, 'id')]

        # Use IDs in the multiselect
        selected_ids = st.multiselect(
            label,
            options=list(id_to_display.keys()),
            default=current_selection_ids,
            format_func=lambda x: id_to_display.get(x, str(x)),
            key=key,
            help=f"Select from {len(options)} available options"
        )
        
        return selected_ids

