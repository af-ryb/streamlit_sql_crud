# streamlit_sql

## Introduction

Creating a CRUD interface can be a tedious and repetitive task. This package is intended to replace all of that with a few lines of code that involves simply creating a sqlalchemy statement and calling the main *SqlUi* class with only 3 required arguments. All extra and advanced features are available by supplying non-required arguments to the class initialization.

When the main class is initialized, it will display the database table data with most of the expected features of a crud interface, so the user will be able to **read, filter, update, create and delete rows** with many useful features. 

It also offers useful information about the data as property like:
- df: The Dataframe displayed in the screen
- selected_rows: The position of selected rows. This is not the row d
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

Run `SqlUi` as the example below:

```python
from streamlit_sql import SqlUi
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

SqlUi(conn=conn,
            read_instance=stmt,
            edit_create_model=db.Invoice,
            available_filter=["name"],
            rolling_total_column="amount",
)

SqlUi(conn, model_opts)
```

!!! warning
    In the statement, **always** include the primary_key column, that should be named *id*

### Interface

- Filter: Open the "Filter" expander and fill the inputs
- Add row: Click on "plus" button (no dataframe row can be selected)
- Edit row: Click on "pencil" button (one and only one dataframe row should be selected)
- Delete row: Click on "trash" button (one or more dataframe rows should be selected)


## Customize

You can adjust the CRUD interface by the select statement you provide to *read_instance* arg and giving optional arguments to the *SqlUi* function. See the docstring for more information or at [documentation webpage](https://edkedk99.github.io/streamlit_sql/api/#streamlit_sql.SqlUi):

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
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="Valid email address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    department: str = Field(..., description="Department name")

class UserUpdateSchema(BaseModel):
    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User's full name")
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="Valid email address")
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
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date

class ProjectCreateSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    start_date: date = Field(..., description="Project start date")
    end_date: Optional[date] = Field(None, description="Project end date")
    budget: float = Field(..., gt=0, description="Project budget in USD")
    
    @field_validator('end_date')
    def end_date_must_be_after_start(cls, v, info):
        if v and 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError('End date must be after start date')
        return v

class ProjectUpdateSchema(BaseModel):
    id: int
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[float] = Field(None, gt=0, description="Project budget in USD")
    
    @field_validator('end_date')
    def end_date_must_be_after_start(cls, v, info):
        if v and 'start_date' in info.data and info.data['start_date'] and v <= info.data['start_date']:
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

## PydanticUi - Standalone Form Component

`PydanticUi` is a powerful, database-agnostic form component that generates Streamlit forms directly from Pydantic models. It provides automatic validation, session state persistence, and customizable widgets.

### Basic Usage

```python
from streamlit_sql import PydanticUi
from pydantic import BaseModel, Field
from typing import Optional
import streamlit as st

class UserSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., pattern=r"^\S+@\S+\.\S+$")
    age: int = Field(..., ge=18, le=120)
    bio: Optional[str] = Field(None, max_length=500)

# Create and render form
ui = PydanticUi(schema=UserSchema, key="user_form")
form_data = ui.render()

if form_data:
    st.success(f"Valid data received: {form_data}")
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `schema` | `Type[BaseModel]` | Required | Pydantic model class defining form fields and validation |
| `key` | `str` | Required | Unique identifier for form widgets (prevents conflicts) |
| `session_state_key` | `Optional[str]` | `None` | Key for session state persistence. If None, defaults to `key` |

### Methods

#### `render() -> Optional[BaseModel]`
Renders the form and returns validated data when all fields are valid.

```python
ui = PydanticUi(schema=MySchema, key="form1")
data = ui.render()
if data:
    # Process validated data
    pass
```

#### `render_with_submit(submit_label: str = "Submit") -> Optional[BaseModel]`
Renders form with a submit button. Returns data only when button is clicked and validation passes.

```python
data = ui.render_with_submit("Create User")
if data:
    # Handle submitted data
    pass
```

#### `render_with_columns(columns: int = 2) -> Optional[BaseModel]`
Renders form fields in a multi-column layout.

```python
# Display form in 3 columns
data = ui.render_with_columns(columns=3)
```

#### Session State Methods

```python
# Get validated data from session
saved_data = ui.get_session_data()

# Update session with new data
ui.update_session_data({"name": "John", "age": 25})

# Clear session data
ui.clear_session_data()

# Get current form data as dictionary (may include invalid data)
current_data = ui.get_form_data()
```

### Widget Customization

Customize form widgets using Pydantic's `json_schema_extra`:

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class AdvancedSchema(BaseModel):
    # Text area widget
    description: str = Field(
        ...,
        json_schema_extra={
            "widget": "text_area",
            "kw": {"height": 150, "help": "Enter detailed description"}
        }
    )
    
    # Selectbox widget
    category: str = Field(
        ...,
        json_schema_extra={
            "widget": "selectbox",
            "kw": {"options": ["Sales", "Marketing", "Engineering"]}
        }
    )
    
    # Multiselect widget
    tags: List[str] = Field(
        default_factory=list,
        json_schema_extra={
            "widget": "multiselect",
            "kw": {"options": ["urgent", "review", "approved", "pending"]}
        }
    )
    
    # Slider widget
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        json_schema_extra={
            "widget": "slider",
            "kw": {"min_value": 1, "max_value": 10, "step": 1}
        }
    )
    
    # Date input
    deadline: date = Field(
        ...,
        json_schema_extra={
            "widget": "date_input",
            "kw": {"min_value": date.today()}
        }
    )
```

### Supported Widget Types

| Widget Type | Pydantic Type | Configuration |
|-------------|---------------|---------------|
| `text_input` | `str` | Default for string fields |
| `text_area` | `str` | Set via `json_schema_extra` or by including `(text_area)` in the field's description |
| `number_input` | `int`, `float` | Default for numeric fields |
| `checkbox` | `bool` | Default for boolean fields |
| `selectbox` | `str`, `Enum` | Requires `options` in `kw` |
| `multiselect` | `List[str]` | Requires `options` in `kw` |
| `slider` | `int`, `float` | Configure min/max/step in `kw` |
| `date_input` | `date` | Default for date fields |
| `time_input` | `time` | Default for time fields |
| `color_picker` | `str` | Set via `json_schema_extra` |

### Session State Persistence

PydanticUi automatically persists form data in Streamlit's session state:

```python
# Form data persists across reruns
ui = PydanticUi(
    schema=ProjectSchema,
    key="project_form",
    session_state_key="project_data"  # Explicit session key
)

# Check if user has previously entered data
if ui.get_session_data():
    st.info("Resuming from saved data")

# Render form - will restore previous values
data = ui.render()

# Clear data when needed
if st.button("Reset Form"):
    ui.clear_session_data()
    st.rerun()
```

### Validation and Error Handling

PydanticUi provides user-friendly validation messages:

```python
from pydantic import BaseModel, Field, field_validator

class RegistrationSchema(BaseModel):
    username: str = Field(..., min_length=3, pattern="^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8)
    confirm_password: str
    
    @field_validator('confirm_password')
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v

ui = PydanticUi(schema=RegistrationSchema, key="register")
data = ui.render()

# Validation errors appear automatically under each field
# Form returns None until all validation passes
```

### Advanced Example: Project Management Form

```python
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class ProjectStatus(str, Enum):
    PLANNING = "Planning"
    ACTIVE = "Active"
    ON_HOLD = "On Hold"
    COMPLETED = "Completed"

class ProjectSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    
    description: str = Field(
        ...,
        json_schema_extra={
            "widget": "text_area",
            "kw": {"height": 200, "placeholder": "Describe the project..."}
        }
    )
    
    status: ProjectStatus = Field(
        default=ProjectStatus.PLANNING,
        json_schema_extra={
            "widget": "selectbox",
            "kw": {"options": [s.value for s in ProjectStatus]}
        }
    )
    
    team_members: List[str] = Field(
        default_factory=list,
        json_schema_extra={
            "widget": "multiselect",
            "kw": {
                "options": ["Alice", "Bob", "Charlie", "David"],
                "help": "Select team members"
            }
        }
    )
    
    budget: float = Field(
        ...,
        gt=0,
        json_schema_extra={
            "widget": "number_input",
            "kw": {"format": "%.2f", "step": 1000.0}
        }
    )
    
    start_date: date = Field(default_factory=date.today)
    
    end_date: Optional[date] = Field(
        None,
        json_schema_extra={
            "widget": "date_input",
            "kw": {"help": "Leave empty for ongoing projects"}
        }
    )
    
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        json_schema_extra={
            "widget": "slider",
            "kw": {"help": "1 = Low, 10 = Critical"}
        }
    )
    
    @field_validator('end_date')
    def validate_dates(cls, v, info):
        if v and 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError('End date must be after start date')
        return v

# Use in Streamlit app
def project_form():
    st.title("Create New Project")
    
    ui = PydanticUi(
        schema=ProjectSchema,
        key="new_project",
        session_state_key="project_draft"
    )
    
    # Render in columns
    with st.container():
        data = ui.render_with_columns(columns=2)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Submit", type="primary"):
            if data:
                # Save to database
                st.success(f"Project '{data.name}' created!")
                ui.clear_session_data()
                st.rerun()
            else:
                st.error("Please fix validation errors")
    
    with col2:
        if st.button("Clear"):
            ui.clear_session_data()
            st.rerun()
    
    with col3:
        if ui.get_session_data():
            st.caption("✓ Draft saved")
```

### Integration with SqlUi

While PydanticUi works standalone, it integrates seamlessly with SqlUi through the `PydanticCrudUi` subclass:

```python
from streamlit_sql import PydanticCrudUi

# Extended version with foreign key support
ui = PydanticCrudUi(
    schema=MySchema,
    key="crud_form",
    foreign_key_options={
        'department_id': {
            'query': select(Department),
            'display_field': 'name',
            'value_field': 'id'
        }
    }
)
```

### Best Practices

1. **Unique Keys**: Always use unique keys to prevent widget conflicts
2. **Session State**: Use explicit session state keys for important forms
3. **Validation**: Leverage Pydantic validators for complex business rules
4. **Widget Selection**: Choose appropriate widgets for better UX
5. **Error Messages**: Provide clear validation messages via Field descriptions
6. **Performance**: For large forms, consider using columns to improve layout

