import streamlit as st
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
        """Validate that Pydantic schema is compatible with SQLAlchemy model
        
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
            
            # Check if all schema fields exist in SQLAlchemy model
            for field_name, field_info in schema_fields.items():
                if field_name not in sqlalchemy_columns:
                    table_name = getattr(model, '__tablename__', model.__name__)
                    logger.warning(f"Field '{field_name}' in {schema.__name__} not found in {table_name}")
                    return False
                    
                # Type compatibility check could be added here
                
            # For update operations, ensure 'id' field is present
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
            
            # Create SQLAlchemy instance
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
        """Determine appropriate Streamlit input type for Pydantic field
        
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
    
    def __init__(self, schema: Type[BaseModel], key_prefix: str = "", foreign_key_options: dict = None):
        self.schema = schema
        self.key_prefix = key_prefix
        self.foreign_key_options = foreign_key_options or {}
        self.field_info = PydanticSQLAlchemyConverter.get_pydantic_field_info(schema)
    
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
            
            # Skip primary key fields for create operations
            if field_name == 'id' and existing_value is None:
                continue
            
            # Get field annotation for better type detection
            annotation = field_info.get('annotation')
            
            # Use our custom implementation for all field types
            field_value = self._render_field_input(
                field_name, field_info, annotation, existing_value, key
            )
            
            # Only include field in form data if it's not None (e.g., ID in create operations)
            if field_value is not None:
                form_data[field_name] = field_value
        
        return form_data
    
    
    
    def _render_field_input(self, field_name: str, field_info: Dict[str, Any], annotation: Any, existing_value: Any, key: str) -> Any:
        """Render appropriate Streamlit input for a field based on its type"""
        
        # Ensure label is always a string
        description = field_info.get('description')
        if description is None or description == '':
            label = field_name.replace('_', ' ').title()
        else:
            label = str(description)
        
        # Handle ID field specially
        if field_name == 'id':
            return self._render_id_field(label, existing_value, key)
        
        # Check for custom foreign key fields first
        elif field_name in self.foreign_key_options:
            return self._render_foreign_key_input(label, field_name, existing_value, key)
        
        # Check for enum types - simplified detection based on streamlit-pydantic approach
        elif self._is_enum_field(annotation):
            return self._render_enum_input(label, annotation, existing_value, key)
        
        # Check for list of enums 
        elif self._is_enum_list_field(annotation):
            return self._render_enum_list_input(label, annotation, existing_value, key)
            
        # Check for regular lists
        elif self._is_list_field(annotation):
            return self._render_list_input(label, annotation, existing_value, key)
            
        # Fall back to basic type detection
        else:
            return self._render_basic_input(label, field_info, existing_value, key)
    
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
    
    def _is_list_field(self, annotation: Any) -> bool:
        """Check if field is a regular list"""
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
    
    def _render_enum_input(self, label: str, annotation: Any, existing_value: Any, key: str) -> Any:
        """Render selectbox for single enum"""
        # Extract actual enum type from Optional[Enum] if needed
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
    
    def _parse_array_string(self, value_str: str) -> list:
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
        """Render basic input types"""
        input_type = PydanticSQLAlchemyConverter.get_streamlit_input_type(field_info)
        
        if input_type == 'text_input':
            return st.text_input(
                label, 
                value=str(existing_value) if existing_value is not None else "", 
                key=key
            )
        elif input_type == 'number_input_int':
            default_val = 0
            if existing_value is not None:
                try:
                    default_val = int(existing_value)
                except (ValueError, TypeError):
                    default_val = 0
            return st.number_input(label, value=default_val, step=1, key=key)
        elif input_type == 'number_input_float':
            default_val = 0.0
            if existing_value is not None:
                try:
                    default_val = float(existing_value)
                except (ValueError, TypeError):
                    default_val = 0.0
            return st.number_input(label, value=default_val, step=0.1, key=key)
        elif input_type == 'checkbox':
            default_val = False
            if existing_value is not None:
                default_val = bool(existing_value)
            return st.checkbox(label, value=default_val, key=key)
        elif input_type == 'date_input':
            return st.date_input(label, value=existing_value, key=key)
        elif input_type == 'text_area_json':
            import json
            json_value = ""
            if existing_value is not None:
                try:
                    if isinstance(existing_value, (dict, list)):
                        json_value = json.dumps(existing_value, indent=2)
                    else:
                        json_value = str(existing_value)
                except:
                    json_value = str(existing_value)
            return st.text_area(label, value=json_value, height=150, key=key, help="Enter valid JSON")
        else:
            # Fallback to text input
            return st.text_input(label, value=str(existing_value) if existing_value is not None else "", key=key)
