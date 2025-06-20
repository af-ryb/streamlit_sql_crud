# streamlit_sql

> **Note**: This project is based on the excellent work of [Eduardo Davalos (edkedk99)](https://github.com/edkedk99) and his [streamlit_sql library](https://github.com/edkedk99/streamlit_sql). We extend our gratitude to the original author for creating such a useful tool for the Streamlit community. This fork adds additional features while maintaining backward compatibility with the original project.

## Introduction

Creating a CRUD interface can be a tedious and repetitive task. This package is intended to replace all of that with a few lines of code that involves simply creating a sqlalchemy statement and calling the main *SqlUi* class with only 3 required arguments. All extra and advanced features are available by supplying non-required arguments to the class initialization.

When the main class is initialized, it will display the database table data with most of the expected features of a crud interface, so the user will be able to **read, filter, update, create and delete rows** with many useful features. 

It also offers useful information about the data as property like:
- df: The Dataframe displayed in the screen
- selected_rows: The position of selected rows. This is not the row id
- qtty_rows: The quantity of all rows after filtering

## Demo

See the package in action [here](https://example-crud.streamlit.app/).

## Features

### READ

- Display as a regular st.dataframe
- Add pagination, displaying only a set of rows each time
- Set the dataframe to be displayed using standard sqlalchemy select statement, where you can JOIN, ORDER BY, WHERE, etc.
- Add a column to show the rolling sum of a numeric column
- Conditional styling if the DataFrame based on each row value. For instance, changing its background color
- Format the number display format.
- Display multiple CRUD interfaces in the same page using unique base_key.
- Show *many-to-one* relation in edit forms with basic editing.
- Log database modification to stderr or to your prefered loguru handler. (can be disabled)
- **NEW**: Support for Pydantic schemas for enhanced validation and separate create/update models

### FILTER

- Filter the data by some columns before presenting the table.
- Let users filter the columns by selecting conditions in the filter expander
- Give possible candidates when filtering using existing values for the columns
- Let users select ForeignKey's values using the string representation of the foreign table, instead of its id number
- **NEW**: Custom foreign key selectboxes with user-friendly display names and flexible queries

### UPDATE

- Users update rows with a dialog opened by selecting the row and clicking the icon
- Text columns offers candidates from existing values
- ForeignKey columns are added by the string representation instead of its id number
- **NEW**: Custom foreign key selectboxes with configurable display fields and filtering
- In Update form, list all ONE-TO-MANY related rows with pagination, where you can directly create and delete related table rows. 
- Log updates to database to stderr or in anyway **loguru** can handle


### CREATE

- Users create new rows with a dialog opened by clicking the create button
- Text columns offers candidates from existing values
- Hide columns to fill by offering default values
- ForeignKey columns are added by the string representation instead of its id number
- **NEW**: Custom foreign key selectboxes with configurable display fields and filtering
- **NEW**: Use Pydantic schemas for enhanced validation and custom field requirements

### DELETE

- Delete one or multiple rows by selecting in DataFrame and clicking the corresponding button. A dialog will list selected rows and confirm deletion.

### VALIDATION (NEW)

- **Pydantic Integration**: Use separate Pydantic models for create and update operations
- **Field Validation**: Leverage Pydantic's validation capabilities (regex, min/max lengths, number ranges, etc.)
- **Type Safety**: Better type checking and IDE support
- **Custom Error Messages**: User-friendly validation error messages
- **Optional Fields**: Different field requirements for create vs update operations



## Requirements

All the requirements you should probably have anyway.

1. streamlit and sqlalchemy
2. **NEW**: pydantic (optional, for enhanced validation)
3. Sqlalchemy models needs a __str__ method
4. Id column should be called "id"
5. Relationships should be added for all ForeignKey columns 


## Basic Usage

Install the package using pip:

```bash
pip install streamlit_sql
```

Run `show_sql_ui` as the example below:

```python
from streamlit_sql import show_sql_ui
from sqlalchemy import select

conn = st.connection("sql", url="<db_url>")

stmt = (
    select(
        db.Invoice.id,
        db.Invoice.Date,
        db.Invoice.amount,
        db.Client.name,
    )
    .join(db.Client)
    .where(db.Invoice.amount > 1000)
    .order_by(db.Invoice.date)
)

show_sql_ui(conn=conn,
            read_instance=stmt,
            edit_create_model=db.Invoice,
            available_filter=["name"],
            rolling_total_column="amount",
)

show_sql_ui(conn, model_opts)
```

!!! warning
    In the statement, **always** include the primary_key column, that should be named *id*

### Interface

- Filter: Open the "Filter" expander and fill the inputs
- Add row: Click on "plus" button (no dataframe row can be selected)
- Edit row: Click on "pencil" button (one and only one dataframe row should be selected)
- Delete row: Click on "trash" button (one or more dataframe rows should be selected)


## Customize

You can adjust the CRUD interface by the select statement you provide to *read_instance* arg and giving optional arguments to the *show_sql_ui* function. See the docstring for more information or at [documentation webpage](https://edkedk99.github.io/streamlit_sql/api/#streamlit_sql.SqlUi):

## Pydantic Schema Integration (NEW)

Starting from version 0.3.3, you can use Pydantic schemas for enhanced validation and separate create/update models.

### Basic Pydantic Usage

```python
from streamlit_sql import SqlUi
from pydantic import BaseModel, Field
from typing import Optional
import streamlit as st

# Define Pydantic schemas
class UserCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="Valid email address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    department: str = Field(..., description="Department name")

class UserUpdateSchema(BaseModel):
    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User's full name")
    email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="Valid email address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    department: Optional[str] = Field(None, description="Department name")

# Use with SqlUi
conn = st.connection("sql", url="your_database_url")

stmt = select(
    db.User.id,
    db.User.name,
    db.User.email,
    db.User.age,
    db.User.department
).order_by(db.User.name)

SqlUi(
    conn=conn,
    read_instance=stmt,
    edit_create_model=db.User,        # ⚠️  Still required - SQLAlchemy model for database operations
    create_schema=UserCreateSchema,   # 🆕 Optional - Pydantic schema for validation during creation
    update_schema=UserUpdateSchema,   # 🆕 Optional - Pydantic schema for validation during updates
    available_filter=["name", "department"],
)
```

### Benefits of Pydantic Integration

1. **Separate Validation Rules**: Different field requirements for create vs update operations
2. **Enhanced Validation**: Use Pydantic validators like regex patterns, min/max values, custom validation functions
3. **Better Error Messages**: User-friendly validation errors with field-specific messages
4. **Type Safety**: Better IDE support and runtime type checking
5. **Documentation**: Schema fields serve as form field documentation
6. **Flexibility**: Exclude sensitive fields or add computed fields
7. **Smart ID Handling**: ID fields are automatically hidden in create forms and shown as read-only in update forms

### Important Notes

- **`edit_create_model` is still required**: This SQLAlchemy model handles the actual database operations
- **Pydantic schemas are optional**: They provide an additional validation layer on top of SQLAlchemy
- **Dual-layer approach**: Pydantic validates user input → SQLAlchemy persists to database
- **Schema compatibility**: Pydantic schema fields must exist in the SQLAlchemy model
- **ID field handling**: Include `id: Optional[str]` in your schemas - it's automatically hidden in create forms and shown as read-only in update forms

### Backward Compatibility

The Pydantic integration is completely optional. Existing code continues to work without any changes:

```python
# This still works exactly as before
SqlUi(
    conn=conn,
    read_instance=stmt,
    edit_create_model=db.User,  # Only this parameter needed
)
```

### Advanced Example with Complex Validation

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date

class ProjectCreateSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    start_date: date = Field(..., description="Project start date")
    end_date: Optional[date] = Field(None, description="Project end date")
    budget: float = Field(..., gt=0, description="Project budget in USD")
    
    @validator('end_date')
    def end_date_must_be_after_start(cls, v, values):
        if v and 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v

class ProjectUpdateSchema(BaseModel):
    id: int
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[float] = Field(None, gt=0, description="Project budget in USD")
    
    @validator('end_date')
    def end_date_must_be_after_start(cls, v, values):
        if v and 'start_date' in values and values['start_date'] and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v

# Use the schemas
SqlUi(
    conn=conn,
    read_instance=select(db.Project),
    edit_create_model=db.Project,           # ⚠️  Still required - SQLAlchemy model for database operations
    create_schema=ProjectCreateSchema,      # 🆕 Optional - Enhanced validation for creation
    update_schema=ProjectUpdateSchema,      # 🆕 Optional - Enhanced validation for updates
)
```

## Text Area Fields for Long Content (NEW)

Starting from version 0.4.0, you can render specific fields as text areas instead of text inputs by adding `(text_area)` to the field description in your Pydantic schemas. This is particularly useful for SQL queries, JSON configurations, and other long text content.

### Usage

Use Pydantic `Field` with a description containing `(text_area)` to render the field as a text area:

```python
from pydantic import BaseModel, Field
from typing import Optional

class QueryConfigCreateSchema(BaseModel):
    name: str = Field(..., description="Configuration name")
    sql_query: str = Field(..., description="SQL Query (text_area)")
    json_config: Optional[str] = Field(None, description="JSON Configuration (text_area)")
    description: Optional[str] = Field(None, description="Description")
    is_active: bool = Field(True, description="Is active")

class QueryConfigUpdateSchema(BaseModel):
    id: Optional[str] = Field(None, description="ID")
    name: str = Field(..., description="Configuration name")
    sql_query: str = Field(..., description="SQL Query (text_area)")
    json_config: Optional[str] = Field(None, description="JSON Configuration (text_area)")
    description: Optional[str] = Field(None, description="Description")
    is_active: bool = Field(True, description="Is active")

# Use with SqlUi
SqlUi(
    conn=conn,
    read_instance=select(db.QueryConfig),
    edit_create_model=db.QueryConfig,
    create_schema=QueryConfigCreateSchema,
    update_schema=QueryConfigUpdateSchema,
)
```

### How It Works

- Fields with `(text_area)` in their description are automatically rendered as `st.text_area`
- Text areas have a default height of 150px for better readability
- Regular fields without `(text_area)` continue to render as standard inputs
- Works with all Pydantic schema types (create, update, read)

### Benefits

1. **Better UX**: Multi-line content is easier to read and edit in text areas
2. **SQL Friendly**: Perfect for SQL queries, JSON configurations, and documentation
3. **Automatic Detection**: Simple pattern-based detection requires no code changes
4. **Backward Compatible**: Existing schemas without the pattern continue to work normally

### Example Fields

Common use cases for text area fields:

```python
# SQL queries
sql_query: str = Field(..., description="SQL Query (text_area)")
fact_query: str = Field(..., description="Fact SQL Query (text_area)")

# JSON configurations  
config_json: str = Field(..., description="JSON Configuration (text_area)")
alert_config_json: str = Field(..., description="Alert JSON Configuration (text_area)")

# Documentation
description: str = Field(..., description="Detailed Description (text_area)")
notes: str = Field(..., description="Additional Notes (text_area)")
```

## Custom Foreign Key Selectboxes (NEW)

Starting from version 0.4.0, you can customize how foreign key fields are displayed in forms by providing custom queries and display fields.

### Problem

By default, foreign key selectboxes use the `__str__` method of related models, which often shows raw IDs or uninformative representations:

```python
# Default behavior - not user-friendly
selectbox options: ["<Template id=abc123>", "<Template id=def456>"]
```

### Solution

Use `foreign_key_options` to specify custom queries and display fields:

```python
from streamlit_sql import SqlUi
from sqlalchemy import select

# Configure custom foreign key display
SqlUi(
    conn=conn,
    read_instance=select(Alert),
    edit_create_model=Alert,
    foreign_key_options={
        'template_id': {
            'query': select(Template),
            'display_field': 'config_name',
            'value_field': 'id'
        },
        'department_id': {
            'query': select(Department).where(Department.active == True),
            'display_field': 'name',
            'value_field': 'id'
        }
    }
)
```

### Configuration Options

Each foreign key field can be configured with:

- **`query`**: SQLAlchemy select statement to fetch available options
- **`display_field`**: Column name to show in the selectbox (user-friendly names)
- **`value_field`**: Column name for the actual value to save (usually 'id')

### Real-World Example

```python
from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

# Models
class ConfigTemplate(Base):
    __tablename__ = 'config_templates'
    id = Column(String, primary_key=True)
    config_name = Column(String, nullable=False)
    description = Column(String)
    is_active = Column(Boolean, default=True)

class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey('config_templates.id'))
    alert_name = Column(String, nullable=False)
    
    template = relationship("ConfigTemplate")

# Usage
SqlUi(
    conn=conn,
    read_instance=select(Alert).options(
        selectinload(Alert.template)  # Eager loading for display
    ),
    edit_create_model=Alert,
    foreign_key_options={
        'template_id': {
            # Custom query with filtering
            'query': select(ConfigTemplate).where(
                ConfigTemplate.is_active == True
            ).order_by(ConfigTemplate.config_name),
            'display_field': 'config_name',  # Show friendly names
            'value_field': 'id'              # Save actual IDs
        }
    }
)
```

### Before vs After

**Before (default behavior):**
```
Template ID: [Select option]
  ▼ <ConfigTemplate id=tpl_123>
    <ConfigTemplate id=tpl_456>
    <ConfigTemplate id=tpl_789>
```

**After (with custom options):**
```
Template ID: [Select option]
  ▼ Customer Analytics Config
    Fraud Detection Setup
    Marketing Campaign Template
```

### Advanced Features

#### Filtered Options
```python
foreign_key_options={
    'category_id': {
        'query': select(Category).where(
            Category.department == 'Sales'
        ).order_by(Category.priority.desc()),
        'display_field': 'name',
        'value_field': 'id'
    }
}
```

#### Computed Display Fields
```python
# Using SQL expressions for display
from sqlalchemy import func

foreign_key_options={
    'user_id': {
        'query': select(
            User.id,
            func.concat(User.first_name, ' ', User.last_name).label('full_name')
        ),
        'display_field': 'full_name',
        'value_field': 'id'
    }
}
```

### Benefits

1. **User-Friendly**: Show meaningful names instead of IDs or object representations
2. **Flexible Queries**: Filter, order, and customize the available options
3. **Data Integrity**: Maintains proper foreign key relationships
4. **Automatic Handling**: Works seamlessly with create/edit forms
5. **Current Value Support**: Preserves existing values when editing records

### Compatibility

- ✅ Works with SQLAlchemy models (full support)
- ⚠️ Pydantic schemas (currently uses default FK handling, custom options planned for future release)
- ✅ Backward compatible (existing code continues to work)

