# streamlit_pydantic_crud

## Introduction

Creating a CRUD interface can be a tedious and repetitive task. This package streamlines the process with just a few lines of code. Simply create a SQLAlchemy statement and call the main *SqlUi* class with only 3 required arguments. Advanced features are available through optional parameters.

When initialized, the main class displays a database table with comprehensive CRUD functionality, allowing users to **read, filter, update, create, and delete rows** with many useful features.

Key enhancements over the original streamlit_sql package:
- **Pydantic validation**: Type-safe forms with automatic validation
- **Enhanced foreign key handling**: Custom selectboxes with user-friendly display names
- **Many-to-many relationships**: Multiselect widgets for association tables
- **Standalone form component**: PydanticUi for database-agnostic forms
- **Session state management**: Form data persistence across reruns
- **Improved error handling**: User-friendly validation messages

## Features

### READ
- Display as a standard st.dataframe with pagination
- Configure using SQLAlchemy select statements (JOIN, ORDER BY, WHERE, etc.)
- **Display fields from joined tables efficiently**
- Add rolling sum columns for numeric data
- Conditional row styling based on values
- Custom number formatting
- Multiple CRUD interfaces per page using unique keys
- View many-to-one relationships in edit forms
- Optional database modification logging
- **Pydantic schemas for data processing and JSON column handling**

### FILTER
- Pre-filter data before display
- User-friendly filter expander with conditions
- Auto-complete with existing column values
- **Filter by fields from joined tables**
- Foreign key filtering by string representation
- **Custom foreign key selectboxes with flexible queries**

### UPDATE
- Edit rows via dialog (select row and click edit icon)
- Text columns with auto-complete from existing values
- Foreign key selection by string representation
- **Configurable foreign key selectboxes**
- **Many-to-many relationship management**
- List one-to-many related rows with inline CRUD
- Update logging support

### CREATE
- Create new rows via dialog
- Auto-complete for text columns
- Hidden columns with default values
- Foreign key selection by string representation
- **Pydantic validation with custom error messages**
- **Many-to-many relationship selection**

#### Copy Functionality

The SqlUi interface includes a copy button that allows duplicating existing rows:
- Select a single row and click the copy button (appears next to edit)
- Creates a new record with all fields pre-populated from the selected row
- The 'id' field is automatically removed to avoid conflicts

**Important: read_schema and copy behavior**

⚠️ **Critical**: When using `read_schema`, only fields included in the schema will be available for copying:

```python
# ❌ PROBLEMATIC: Missing fields in read schema
class AlertReadSchema(BaseModel):
    alert_name: str
    is_active: bool
    # fact_query field is missing!

SqlUi(
    conn=conn,
    model=Alert,
    read_schema=AlertReadSchema,  # fact_query won't be copied!
)
```

```python
# ✅ SOLUTION: Include all fields you want to copy
class AlertReadSchema(BaseModel):
    alert_name: str
    is_active: bool
    fact_query: str  # Now available for copying
```

**Why this happens**: The copy function retrieves data from the displayed dataframe, which only contains fields defined in the read_schema. Missing fields won't be available for copying, even if they exist in the database.

### DELETE
- Delete single or multiple rows
- Confirmation dialog with selected row preview

### VALIDATION
- **Pydantic Integration**: Separate models for create/update operations
- **Field Validation**: Regex patterns, min/max values, custom validators
- **Type Safety**: Enhanced IDE support and runtime checking
- **Custom Messages**: User-friendly validation errors
- **Flexible Requirements**: Different field requirements per operation

## Requirements

1. Python 3.12+
2. Core dependencies: streamlit, sqlalchemy, pandas, pydantic (≥2.0)
3. SQLAlchemy models require a `__str__` method
4. Primary key column must be named "id"
5. Foreign key relationships must be defined

## Installation

```bash
pip install streamlit_pydantic_crud
```

## Basic Usage

```python
from streamlit_pydantic_crud import SqlUi
from sqlalchemy import select
import streamlit as st

# Database connection
conn = st.connection("sql", url="<db_url>")

# Define query
stmt = (
    select(
        db.Invoice.id,
        db.Invoice.date,
        db.Invoice.amount,
        db.Client.name,
    )
    .join(db.Client)
    .where(db.Invoice.amount > 1000)
    .order_by(db.Invoice.date)
)

# Create CRUD interface
SqlUi(
    conn=conn,
    model=db.Invoice,  # Single model for both read and write
    available_filter=["name"],
    rolling_total_column="amount",
)
```

> **Note**: Always include the primary key column (id) in your select statement

### Interface Controls
- **Filter**: Open the "Filter" expander
- **Add**: Click the "+" button (no row selected)
- **Edit**: Click the "pencil" button (one row selected)
- **Delete**: Click the "trash" button (one or more rows selected)

## Pydantic Schema Integration

Enhanced validation using Pydantic schemas for create and update operations:

```python
from streamlit_pydantic_crud import SqlUi
from pydantic import BaseModel, Field
from typing import Optional

# Create schema - all fields required
class UserCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: Optional[int] = Field(None, ge=0, le=120)
    department: str

# Update schema - all fields optional except id
class UserUpdateSchema(BaseModel):
    id: int
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: Optional[int] = Field(None, ge=0, le=120)
    department: Optional[str] = None

# Use with SqlUi
SqlUi(
    conn=conn,
    model=db.User,  # SQLAlchemy model
    create_schema=UserCreateSchema,  # Pydantic validation for creation
    update_schema=UserUpdateSchema,  # Pydantic validation for updates
    available_filter=["name", "department"],
)
```

### Benefits
- Separate validation rules for create vs update
- Enhanced validation (regex, ranges, custom validators)
- Better error messages
- Type safety and IDE support
- Field documentation
- Backward compatible (Pydantic schemas are optional)

## Custom Foreign Key Selectboxes

Configure user-friendly selectboxes for foreign key fields:

```python
SqlUi(
    conn=conn,
    model=Alert,
    foreign_key_options={
        'template_id': {
            'query': select(Template).where(Template.active == True),
            'display_field': 'config_name',  # Show this field
            'value_field': 'id'              # Save this value
        }
    }
)
```

### Result
Instead of: `<Template id=abc123>`  
You get: `Customer Analytics Config`

## Many-to-Many Relationships

Manage association tables with multiselect widgets:

```python
# Pydantic schemas with many-to-many field
class PostCreateSchema(BaseModel):
    title: str
    content: str
    tags: List[int] = Field(default_factory=list, description="Tag IDs")

# Configure SqlUi
SqlUi(
    conn=conn,
    model=Post,
    create_schema=PostCreateSchema,
    many_to_many_fields={
        'tags': {
            'relationship': 'tags',      # SQLAlchemy relationship
            'display_field': 'name',     # Display tag names
            'filter': lambda q: q.filter(Tag.active == True)  # Optional
        }
    }
)
```

## JOIN Fields Support

Display and filter fields from joined tables efficiently:

```python
# Create a SELECT statement with JOINs
read_stmt = (
    select(
        Alert.id,
        Alert.alert_name,
        Alert.threshold,
        Template.app_name,
        Template.platform,
        Template.metric_name
    )
    .join(Template, Alert.template_id == Template.id)
)

# Use with SqlUi - joined fields are automatically available for filtering
SqlUi(
    conn=conn,
    read_instance=read_stmt,
    edit_create_model=Alert,
    available_filter=["alert_name", "app_name", "platform", "metric_name"],
)
```

### Benefits
- **Performance**: Direct JOINs are more efficient than loading relationships
- **Filtering**: All joined fields can be filtered using the standard filter interface
- **No Property Methods**: No need for @property methods or selectinload()
- **Complex Queries**: Supports multiple joins and complex SQL queries

### Handling Column Name Conflicts
Use `.label()` to rename columns when joining tables with identical column names:

```python
read_stmt = (
    select(
        Order,
        Customer.name.label('customer_name'),
        Product.name.label('product_name')
    )
    .join(Customer).join(Product)
)
```

### Important: read_schema Limitations with JOINs

⚠️ **Critical Note**: When using JOIN queries with fields from multiple tables, `read_schema` has important limitations:

```python
# ❌ PROBLEMATIC: read_schema with joined fields
class ProjectWithDepartmentSchema(BaseModel):
    id: int
    name: str
    # These fields from joined table will cause validation errors
    department_name: str  # From Department table
    department_type: str  # From Department table

SqlUi(
    conn=conn,
    read_instance=select(Project, Department.name.label('department_name')).join(Department),
    edit_create_model=Project,
    read_schema=ProjectWithDepartmentSchema,  # ❌ Will fail validation
)
```

```python
# ✅ SOLUTION 1: Omit read_schema for JOIN queries
SqlUi(
    conn=conn,
    read_instance=select(
        Project.id,
        Project.name,
        Project.budget,
        Department.name.label('department_name'),
        Department.department_type
    ).join(Department),
    edit_create_model=Project,
    # No read_schema - joined fields will still be displayed and filterable
)
```

```python
# ✅ SOLUTION 2: read_schema with only base model fields
class ProjectOnlySchema(BaseModel):
    id: int
    name: str
    budget: Decimal
    # Only fields that exist in Project model

SqlUi(
    conn=conn,
    read_instance=select(
        Project.id,
        Project.name, 
        Project.budget,
        Department.name.label('department_name')  # Will be displayed but not in schema
    ).join(Department),
    edit_create_model=Project,
    read_schema=ProjectOnlySchema,  # ✅ Only base model fields
)
```

**Why this happens**: Schema validation checks that all schema fields exist as columns, relationships, or properties in the base SQLAlchemy model. Joined fields don't exist in the base model, causing validation to fail.

**Best Practice**: For JOIN queries, either omit `read_schema` entirely or only include fields from the base model. Joined fields will still be displayed, filtered, and formatted correctly.

### Calculated Fields in JOIN Queries

You can add calculated fields using SQL expressions in your SELECT statements:

```python
from sqlalchemy import func

# JOIN with calculated fields
read_stmt = (
    select(
        Project.id,
        Project.name,
        Project.budget,
        Department.name.label('department_name'),
        Department.budget.label('department_budget'),
        
        # Calculated field: percentage
        (Project.budget / Department.budget * 100).label('budget_percent'),
        
    )
    .join(Department, Project.department_id == Department.id)
)

SqlUi(
    conn=conn,
    read_instance=read_stmt,
    edit_create_model=Project,
    available_filter=["name", "department_name", "status_description", "budget_percent"],
    df_style_formatter={
        "budget": "${:,.2f}",
        "budget_percent": "{:.1f}%",
        "days_remaining": "{} days"
    }
)
```

**Calculated Fields Features**:
- Mathematical operations between columns from different tables
- CASE statements for conditional logic  
- Date/time calculations with proper NULL handling
- Window functions for analytics
- All calculated fields can be included in filters and formatting

## Filtering with JOIN Statements

When using JOIN statements, the filtering system automatically handles both direct table columns and joined columns efficiently.

### How JOIN Filtering Works

The filtering implementation uses a two-stage approach when `many_to_many_fields` are present:

1. **Filter First**: Executes the joined query with all applied filters to get the correct filtered results
2. **Load Relationships**: For entities that have many-to-many relationships, loads the relationship data separately for only the filtered entities
3. **Merge Results**: Combines the filtered data with the relationship data

### Example with Joined Table Filtering

```python
# JOIN statement with labeled columns for filtering
read_stmt = (
    select(
        AlertConfiguration,
        Template.app_name.label('app_name'),
        Template.platform.label('platform'), 
        Template.metric_name.label('metric_name')
    )
    .select_from(AlertConfiguration)
    .join(Template, AlertConfiguration.template_id == Template.id)
    .options(
        selectinload(AlertConfiguration.rules),
        selectinload(AlertConfiguration.template)
    )
)

SqlUi(
    conn=conn,
    read_instance=read_stmt,
    edit_create_model=AlertConfiguration,
    many_to_many_fields={
        'rules': {
            'relationship': 'rules',
            'display_field': 'name'
        }
    },
    available_filter=['is_active', 'app_name', 'platform', 'metric_name'],
)
```

### Key Benefits

- **Correct Filtering**: Filters are applied to the base query, ensuring accurate results
- **Performance Optimized**: Relationships loaded only for filtered entities, not all entities
- **Seamless Integration**: Works transparently with existing SqlUi features
- **Complex Queries Supported**: Handles multiple JOINs, subqueries, and CTEs

### Technical Details

The filtering process:

1. **CTE Creation**: Your JOIN query becomes a Common Table Expression (CTE)
2. **Filter Application**: User selections are applied as WHERE conditions to the CTE
3. **Smart Execution**: When `many_to_many_fields` are configured:
   - Executes filtered statement to get base results
   - Extracts entity IDs from filtered results  
   - Loads full entities with relationships for those IDs only
   - Merges filtered data with relationship data
4. **Result Display**: Shows filtered results with all relationship data intact

This approach ensures that filtering works correctly while maintaining full relationship functionality and optimal performance.

## PydanticUi - Standalone Forms

Create Streamlit forms from Pydantic models without database dependencies:

```python
from streamlit_pydantic_crud import PydanticUi
from pydantic import BaseModel, Field
from typing import Optional

class ProjectSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., description="(text_area)")  # Custom widget
    budget: float = Field(..., gt=0)
    priority: int = Field(default=5, ge=1, le=10)

# Create form (session_state_key defaults to key if omitted)
ui = PydanticUi(
    schema=ProjectSchema,
    key="project_form",
    session_state_key="my_project",  # optional, custom session state key
)

# Option 1: Render with submit button (wraps in st.form)
model, submitted = ui.render_with_submit("Create Project")
if submitted and model:
    st.success(f"Project '{model.name}' created!")
    ui.clear_session_data()

# Option 2: Render without st.form (standalone widgets)
model = ui.render()
if model:
    st.write(model.model_dump())
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `render()` | `Optional[T]` | Render form fields as standalone widgets (no `st.form` wrapper) |
| `render_with_submit(label, on_submit, on_submit_args, on_submit_kwargs)` | `Tuple[Optional[T], bool]` | Render inside `st.form` with a submit button |
| `render_with_columns(columns)` | `Optional[T]` | Render form fields distributed across multiple columns |
| `update_session_data(data)` | `None` | Pre-populate form with a dict or Pydantic model (edit/update mode) |
| `get_session_data()` | `Optional[T]` | Get validated model instance from session state |
| `get_form_data()` | `Dict[str, Any]` | Get raw form data as a dictionary |
| `collect_widget_data()` | `Optional[T]` | Read committed widget values from session state (useful in callbacks) |
| `clear_session_data()` | `None` | Reset form by clearing session state |

### on_submit Callback

The `render_with_submit` method accepts an `on_submit` callback that runs when the form is submitted (via `st.form_submit_button`'s `on_click`). Use `collect_widget_data()` inside the callback to access validated form data:

```python
def handle_submit(db_session, table_name):
    model = ui.collect_widget_data()
    if model:
        db_session.add(model)
        db_session.commit()

model, submitted = ui.render_with_submit(
    "Save",
    on_submit=handle_submit,
    on_submit_args=(session,),
    on_submit_kwargs={"table_name": "projects"},
)
```

### Pre-populating Forms

Use `update_session_data()` to fill form fields for edit/update workflows. Accepts a dict or a Pydantic model instance:

```python
# Load existing record
existing = ProjectSchema(name="Alpha", description="Desc", budget=1000.0, priority=3)
ui.update_session_data(existing)

# Or from a dictionary
ui.update_session_data({"name": "Alpha", "budget": 1000.0})
```

### Multi-column Layout

```python
ui = PydanticUi(schema=ProjectSchema, key="col_form")
model = ui.render_with_columns(columns=3)
```

### Type Auto-detection

PydanticUi automatically selects the appropriate Streamlit widget based on the Python type annotation:

| Python Type | Widget | Notes |
|-------------|--------|-------|
| `str` | `st.text_input` | Use `description="(text_area)"` for multiline |
| `int` | `st.number_input` | `step=1` |
| `float` | `st.number_input` | `step=0.1` |
| `bool` | `st.checkbox` | |
| `date` | `st.date_input` | |
| `datetime` | `st.datetime_input` | |
| `Decimal` | `st.number_input` | `step=0.01` |
| `Enum` | `st.selectbox` | Options from enum members |
| `list` / `List[str]` | `st.multiselect` | |
| `List[Enum]` | `st.multiselect` | Options from enum members |
| `dict` | `st.text_area` | JSON input with validation |

### Widget Customization

Override auto-detected widgets using `json_schema_extra` with `"widget"` and `"kw"` keys:

```python
class AdvancedSchema(BaseModel):
    # Text area
    notes: str = Field(
        ...,
        json_schema_extra={
            "widget": "text_area",
            "kw": {"height": 150}
        }
    )

    # Selectbox
    category: str = Field(
        ...,
        json_schema_extra={
            "widget": "selectbox",
            "kw": {"options": ["Sales", "Marketing", "Tech"]}
        }
    )

    # Slider
    rating: int = Field(
        default=5,
        json_schema_extra={
            "widget": "slider",
            "kw": {"min_value": 1, "max_value": 10}
        }
    )

    # Radio buttons
    status: str = Field(
        ...,
        json_schema_extra={
            "widget": "radio",
            "kw": {"options": ["Draft", "Published", "Archived"]}
        }
    )

    # Datetime input
    scheduled_at: datetime = Field(
        ...,
        json_schema_extra={
            "widget": "datetime_input",
            "kw": {}
        }
    )
```

All available widget types for `json_schema_extra`:

| Widget | Key kwargs |
|--------|-----------|
| `text_input` | `disabled`, `max_chars`, `placeholder` |
| `text_area` | `height`, `max_chars`, `placeholder` |
| `number_input` | `min_value`, `max_value`, `step` |
| `selectbox` | `options` |
| `multiselect` | `options`, `max_selections` |
| `checkbox` | |
| `date_input` | `min_value`, `max_value` |
| `datetime_input` | |
| `slider` | `min_value`, `max_value`, `step` |
| `radio` | `options` |

### Dynamic Schema Creation

Create PydanticUi forms directly from JSON schemas with field options:

```python
from streamlit_pydantic_crud import PydanticUi

# JSON schema (typically from API response)
json_schema = {
    "properties": {
        "task_type": {
            "type": "string",
            "default": "data_processing",
            "widget": "text_input",
            "kw": {"disabled": True}
        },
        "start_date": {
            "anyOf": [
                {"type": "string", "format": "date"},
                {"type": "null"}
            ],
            "default": None
        },
        "tags": {
            "anyOf": [
                {"type": "array", "items": {"type": "string"}},
                {"type": "null"}
            ],
            "widget": "multiselect"
        }
    },
    "required": ["task_type"]
}

# Field options for widgets
field_options = {
    "tags": ["analytics", "processing", "reporting", "automation"]
}

# Create form directly from JSON schema
ui = PydanticUi.from_json_schema(
    json_schema=json_schema,
    field_options=field_options,
    key="dynamic_form",
    model_name="TaskConfig"
)

# Use normally
model_instance, submitted = ui.render_with_submit("Submit Task")
if submitted and model_instance:
    # Process the validated data
    st.write(model_instance.model_dump())
```

#### Benefits of `from_json_schema`

- **Single-step creation**: No need to manually create Pydantic models first
- **Type preservation**: Optional fields maintain correct types (`Optional[date]`, `Optional[List[str]]`)
- **Widget integration**: Field options are automatically applied to appropriate widgets
- **API compatibility**: Perfect for forms generated from API schema responses
- **Backward compatible**: Existing `PydanticUi(schema=MyModel)` usage unchanged

#### Use Cases

1. **Dynamic API forms**: Create forms from API-provided schemas
2. **Configuration interfaces**: Build forms from JSON configuration schemas
3. **Multi-tenant applications**: Different form schemas per tenant
4. **Schema evolution**: Handle changing schemas without code updates

```python
# Example: API-driven form creation
def create_task_form(task_type: str):
    # Get schema from API
    api_response = requests.get(f"/api/schemas/{task_type}")
    schema_data = api_response.json()

    # Create form directly
    ui = PydanticUi.from_json_schema(
        json_schema=schema_data["py_schema"],
        field_options=schema_data["field_options"],
        key=f"task_form_{task_type}"
    )

    return ui.render_with_submit("Create Task")
```

## Advanced Configuration

See the [API documentation](https://github.com/af-ryb/streamlit_sql_crud) for complete parameter documentation and advanced features.

## Changes from Original

This fork significantly extends the original streamlit_sql package with:
- Pydantic integration for validation
- Enhanced foreign key handling
- Many-to-many relationship support
- Standalone form component (PydanticUi)
- Improved error messages and user experience
- Modern Python 3.12+ support
- Better type safety

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
