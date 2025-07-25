import streamlit as st
from typing import Type, Dict, Any, Optional, Union, TypeVar, Generic, Tuple
from pydantic import BaseModel, ValidationError
from loguru import logger

from streamlit_pydantic_crud.pydantic_utils import PydanticInputGenerator

T = TypeVar('T', bound=BaseModel)


class PydanticUi(Generic[T]):
    """Standalone Pydantic-based Streamlit form generator.
    Creates dynamic forms from Pydantic models with automatic validation,
    session state persistence, and flexible widget customization.
    """
    def __init__(
        self,
        schema: Type[T],
        key: str,
        session_state_key: Optional[str] = None,
    ):
        """Initialize PydanticUi.
        
        Args:
            schema: Pydantic model class to generate form from
            key: Unique key for the form (used for widget keys)
            session_state_key: Key for session state persistence (defaults to key)
        """
        self.schema = schema
        self.key = key
        self.session_state_key = session_state_key or key

        self.input_generator = PydanticInputGenerator(schema=schema, key_prefix=key)
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state for form data persistence."""
        if self.session_state_key not in st.session_state:
            st.session_state[self.session_state_key] = {}
    
    def render(self) -> Optional[T]:
        """Render form UI and return validated model instance.
        
        Returns:
            Validated Pydantic model instance or None if validation fails
        """
        try:
            # Get existing values from session state
            existing_values = st.session_state.get(self.session_state_key, {})
            
            # Generate form data using input generator
            form_data = self.input_generator.generate_form_data(existing_values)
            
            # Update session state with current form data
            st.session_state[self.session_state_key] = form_data
            
            # Validate and return model instance
            if self._has_required_fields(form_data):
                try:
                    model_instance = self.schema(**form_data)
                    return model_instance
                except ValidationError as e:
                    self._display_validation_errors(e)
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error rendering PydanticUi form: {e}")
            st.error(f"Form rendering error: {str(e)}")
            return None
    
    def _has_required_fields(self, form_data: Dict[str, Any]) -> bool:
        """Check if all required fields have values."""
        for field_name, field_info in self.schema.model_fields.items():
            if field_info.is_required() and field_name not in form_data:
                return False
            if field_info.is_required() and form_data.get(field_name) in [None, "", []]:
                return False
        return True
    
    def _display_validation_errors(self, error: ValidationError):
        """Display validation errors in a user-friendly format."""
        st.error("Validation errors:")
        for err in error.errors():
            field_name = " → ".join(str(loc) for loc in err['loc'])
            st.error(f"**{field_name}**: {err['msg']}")
    
    def get_session_data(self) -> Optional[T]:
        """Get validated data from session state as model instance.
        
        Returns:
            Validated Pydantic model instance or None if data is invalid
        """
        try:
            session_data = st.session_state.get(self.session_state_key, {})
            if not session_data:
                return None
            
            # Validate session data
            model_instance = self.schema(**session_data)
            return model_instance
            
        except ValidationError:
            return None
        except Exception as e:
            logger.error(f"Error getting session data: {e}")
            return None
    
    def clear_session_data(self):
        """Clear session state data for this form."""
        if self.session_state_key in st.session_state:
            del st.session_state[self.session_state_key]
        
        # Also clear individual widget keys
        for field_name in self.schema.model_fields.keys():
            widget_key = f"{self.key}_{field_name}"
            if widget_key in st.session_state:
                del st.session_state[widget_key]
    
    def update_session_data(self, data: Union[Dict[str, Any], BaseModel, None]):
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
            
            # Clear existing widget keys first to avoid Streamlit error
            for field_name in self.schema.model_fields.keys():
                widget_key = f"{self.key}_{field_name}"
                if widget_key in st.session_state:
                    del st.session_state[widget_key]
            
            # Update the main session state key
            st.session_state[self.session_state_key] = data_dict
            
            # Note: Individual widget keys will be populated on next render
            # We cannot set them here as widgets may already be instantiated
            
        except Exception as e:
            logger.error(f"Error updating session data: {e}")
    
    def get_form_data(self) -> Dict[str, Any]:
        """Get current form data as dictionary.
        
        Returns:
            Dictionary of current form field values
        """
        return st.session_state.get(self.session_state_key, {})
    
    def render_with_submit(self, submit_label: str = "Submit") -> Tuple[Optional[T], bool]:
        """Render form with submit button and return validated data with submit status.
        
        Args:
            submit_label: Label for the submit button
            
        Returns:
            Tuple of (validated Pydantic model instance or None, submit button pressed status)
        """
        with st.form(key=f"{self.key}_form"):
            # Render form fields
            model_instance = self.render()
            
            # Submit button
            submitted = st.form_submit_button(submit_label)
            
            return model_instance, submitted
    
    def render_with_columns(self, columns: int = 2) -> Optional[T]:
        """Render form fields in columns layout.
        
        Args:
            columns: Number of columns to use
            
        Returns:
            Validated Pydantic model instance or None if validation fails
        """
        try:
            # Get existing values from session state
            existing_values = st.session_state.get(self.session_state_key, {})
            
            # Create columns
            cols = st.columns(columns)
            
            # Distribute fields across columns
            field_names = list(self.schema.model_fields.keys())
            form_data = {}
            
            for i, field_name in enumerate(field_names):
                col_index = i % columns
                field_info = self.input_generator.field_info[field_name]
                
                with cols[col_index]:
                    # Generate field input
                    key = f"{self.key}_{field_name}"
                    existing_value = existing_values.get(field_name)
                    annotation = field_info.get('annotation')
                    
                    field_value = self.input_generator._render_field_input(
                        field_name, field_info, annotation, existing_value, key
                    )
                    
                    if field_value is not None:
                        form_data[field_name] = field_value
            
            # Update session state
            st.session_state[self.session_state_key] = form_data
            
            # Validate and return model instance
            if self._has_required_fields(form_data):
                try:
                    model_instance = self.schema(**form_data)
                    return model_instance
                except ValidationError as e:
                    self._display_validation_errors(e)
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error rendering PydanticUi form with columns: {e}")
            st.error(f"Form rendering error: {str(e)}")
            return None


class PydanticCrudUi(PydanticUi[T]):
    """Pydantic UI component with CRUD-specific functionality.
    
    Extends PydanticUi with foreign key support for SqlUi components.
    """
    
    def __init__(
        self,
        schema: Type[T],
        key: str,
        session_state_key: Optional[str] = None,
        foreign_key_options: Optional[Dict] = None,
        many_to_many_fields: Optional[Dict] = None,
    ):
        """Initialize PydanticCrudUi for CRUD operations.
        
        Args:
            schema: Pydantic model class to generate form from
            key: Unique key for the form (used for widget keys)
            session_state_key: Key for session state persistence (defaults to key)
            foreign_key_options: Configuration for foreign key fields
            many_to_many_fields: Configuration for many-to-many fields
        """
        # Initialize parent without input generator
        super().__init__(schema=schema, key=key, session_state_key=session_state_key)
        
        # Store foreign key options
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}
        
        # Reinitialize input generator with foreign key support
        self.input_generator = PydanticInputGenerator(
            schema=schema,
            key_prefix=key,
            foreign_key_options=self.foreign_key_options,
            many_to_many_fields=self.many_to_many_fields,
        )

        self._init_session_state()
