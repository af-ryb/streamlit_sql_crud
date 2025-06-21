## Core Development Rules

### Code Quality
Type hints required for all code  
Public APIs must have docstrings  
Functions must be focused and small  
Follow existing patterns exactly  
Line length: 88 chars maximum  
Comments: two lines maximum, always use triple quotes, written in english  


###  Code Style
PEP 8 naming (snake_case for functions/variables)  
Class names in PascalCase  
Constants in UPPER_SNAKE_CASE  
Document with docstrings  
Use f-strings for formatting  


### Testing Requirements
New features require tests  
Tests must be written in pytest  
Keep test files in separate directory, with name `tests` 

## Development Philosophy
- **Simplicity**: Write simple, straightforward code
- **Readability**: Make code easy to understand
- **Performance**: Consider performance without sacrificing readability
- **Maintainability**: Write code that's easy to update
- **Testability**: Ensure code is testable
- **Reusability**: Create reusable components and functions
- **Less Code = Less Debt**: Minimize code footprint


## Coding Best Practices
- **Make import on the top** of the file, never make import inside the function
- **Use comments**: Use comments to explain your code
- **Early Returns**: Use to avoid nested conditions
- **Descriptive Names**: Use clear variable/function names (prefix handlers with "handle")
- **Constants Over Functions**: Use constants where possible
- **DRY Code**: Don't repeat yourself
- **Functional Style**: Prefer functional, immutable approaches when not verbose
- **Minimal Changes**: Only modify code related to the task at hand
- **Function Ordering**: Define composing functions before their components
- **Simplicity**: Prioritize simplicity and readability over clever solutions
- **Build Iteratively** Start with minimal functionality and verify it works before adding complexity
- **Run Tests**: Test your code frequently with realistic inputs and validate outputs
- **Functional Code**: Use functional and stateless approaches where they improve clarity
- **Clean logic**: Keep core logic clean and push implementation details to the edges
- **File Organsiation**: Balance file organization with simplicity - use an appropriate number of files for the project scale
