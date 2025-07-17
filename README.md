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

# Create form
ui = PydanticUi(schema=ProjectSchema, key="project_form")

# Render with submit button
data = ui.render_with_submit("Create Project")
if data:
    st.success(f"Project '{data.name}' created!")
    ui.clear_session_data()
```

### Widget Customization

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
