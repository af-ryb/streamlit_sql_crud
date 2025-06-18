from typing import Optional, Union, Type
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import DeclarativeBase

class BaseSchema(BaseModel):
    """Base schema with common configuration for StreamlitSQL CRUD operations"""
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        use_enum_values=True
    )

class CreateSchemaBase(BaseSchema):
    """Base class for create schemas
    
    Create schemas should not include the 'id' field as it's typically auto-generated
    by the database. Include only fields that are required or optional for creation.
    
    Example:
        class UserCreateSchema(CreateSchemaBase):
            name: str = Field(..., min_length=1, max_length=100)
            email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
            age: Optional[int] = Field(None, ge=0, le=120)
    """
    pass

class UpdateSchemaBase(BaseSchema):
    """Base class for update schemas
    
    Update schemas should include the 'id' field to identify the record to update.
    Other fields can be optional to allow partial updates.
    
    Example:
        class UserUpdateSchema(UpdateSchemaBase):
            id: int = Field(..., description="Record ID")
            name: Optional[str] = Field(None, min_length=1, max_length=100)
            email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
            age: Optional[int] = Field(None, ge=0, le=120)
    """
    id: int = Field(..., description="Record ID")

# Type aliases for better readability
CreateSchema = Union[Type[BaseModel], Type[CreateSchemaBase]]
UpdateSchema = Union[Type[BaseModel], Type[UpdateSchemaBase]]