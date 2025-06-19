import streamlit as st
import re
from typing import Type, Dict, Any, Optional, Union, get_origin, get_args
from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.types import Enum as SQLEnum, Numeric
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
    
    def __init__(self, schema: Type[BaseModel], key_prefix: str = ""):
        self.schema = schema
        self.key_prefix = key_prefix
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
                
            input_type = PydanticSQLAlchemyConverter.get_streamlit_input_type(field_info)
            # Ensure label is always a string
            description = field_info.get('description')
            if description is None or description == '':
                label = field_name.replace('_', ' ').title()
            else:
                label = str(description)
            
            if input_type == 'text_input':
                form_data[field_name] = st.text_input(
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
                form_data[field_name] = st.number_input(
                    label, 
                    value=default_val, 
                    step=1, 
                    key=key
                )
            elif input_type == 'number_input_float':
                default_val = 0.0
                if existing_value is not None:
                    try:
                        default_val = float(existing_value)
                    except (ValueError, TypeError):
                        default_val = 0.0
                form_data[field_name] = st.number_input(
                    label, 
                    value=default_val, 
                    step=0.1, 
                    key=key
                )
            elif input_type == 'checkbox':
                default_val = False
                if existing_value is not None:
                    default_val = bool(existing_value)
                form_data[field_name] = st.checkbox(
                    label, 
                    value=default_val, 
                    key=key
                )
            elif input_type == 'date_input':
                form_data[field_name] = st.date_input(
                    label, 
                    value=existing_value, 
                    key=key
                )
            elif input_type == 'text_area_json':
                import json
                # Handle JSON fields with text area
                json_value = ""
                if existing_value is not None:
                    try:
                        if isinstance(existing_value, (dict, list)):
                            json_value = json.dumps(existing_value, indent=2)
                        else:
                            json_value = str(existing_value)
                    except:
                        json_value = str(existing_value)
                        
                form_data[field_name] = st.text_area(
                    label,
                    value=json_value,
                    height=150,
                    key=key,
                    help="Enter valid JSON"
                )
            elif input_type == 'multiselect':
                # Handle list/array fields with multiselect
                current_values = []
                if existing_value is not None:
                    if isinstance(existing_value, (list, tuple)):
                        current_values = list(existing_value)
                    elif isinstance(existing_value, str):
                        # Handle PostgreSQL array format: {val1,val2} or {\"val1\",\"val2\"}
                        value_str = existing_value.strip()
                        
                        if value_str.startswith('{') and value_str.endswith('}'):
                            value_str = value_str[1:-1]  # Remove braces
                            
                        # Handle quoted values and unquoted values
                        if value_str:
                            # Split by comma, but handle quoted strings
                            parts = re.findall(r'"([^"]*)"|\\b([^,]+)\\b', value_str)
                            for quoted, unquoted in parts:
                                val = quoted if quoted else unquoted
                                if val.strip():
                                    current_values.append(val.strip())
                        
                        # Fallback: simple comma split
                        if not current_values and value_str:
                            current_values = [v.strip() for v in value_str.split(',') if v.strip()]
                
                # Check if this is a List[Enum] type and extract enum options
                options = current_values.copy()
                enum_options = []
                annotation = field_info.get('annotation', None)
                
                # Try to extract enum options from List[EnumType] annotations
                if annotation and hasattr(annotation, '__args__'):
                    args = getattr(annotation, '__args__', ())
                    if args and len(args) > 0:
                        enum_type = args[0]
                        if hasattr(enum_type, '__members__'):
                            # This is an enum type
                            enum_options = [member.value for member in enum_type.__members__.values()]
                            options.extend([opt for opt in enum_options if opt not in options])
                
                # Use multiselect with accept_new_options for flexibility
                form_data[field_name] = st.multiselect(
                    label,
                    options=options,
                    default=current_values,
                    accept_new_options=True if not enum_options else False,  # Restrict to enum values if enum detected
                    key=key,
                    help="Select existing options or type new ones, if preselected option does not exists"
                )
            else:
                # Fallback to text input
                form_data[field_name] = st.text_input(
                    label, 
                    value=str(existing_value) if existing_value is not None else "", 
                    key=key
                )
        
        return form_data
