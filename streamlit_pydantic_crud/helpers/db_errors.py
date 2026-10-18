"""Turn database exceptions into user-friendly messages."""


def format_database_error(error: Exception) -> str:
    """Format database errors into user-friendly messages.

    Args:
        error: Database exception to format

    Returns:
        User-friendly error message string
    """
    error_str = str(error)

    # Handle NULL identity key error (auto-generated primary keys)
    if "NULL identity key" in error_str:
        return (
            "⚠️ Database Configuration Issue: This table appears to use auto-generated IDs, "
            "but the database is not properly configured for ID generation. "
            "Please ensure your database table has auto-increment/sequence enabled for the ID column, "
            "or exclude the ID field from your create schema."
        )

    # Handle unique constraint violations
    if "UNIQUE constraint failed" in error_str or "duplicate key" in error_str.lower():
        return (
            "❌ Duplicate Entry: A record with these values already exists. "
            "Please check for duplicate entries and try again."
        )

    # Handle foreign key constraint violations
    if (
        "FOREIGN KEY constraint failed" in error_str
        or "foreign key" in error_str.lower()
    ):
        return (
            "🔗 Invalid Reference: One or more referenced records don't exist. "
            "Please ensure all referenced data is valid and try again."
        )

    # Handle NOT NULL constraint violations
    if (
        "NOT NULL constraint failed" in error_str
        or "cannot be null" in error_str.lower()
        or "violates not-null constraint" in error_str
    ):
        return (
            "📝 Missing Required Fields: Some required fields are missing. "
            "Please fill in all required fields and try again."
        )

    # Handle connection/timeout errors
    if "connection" in error_str.lower() or "timeout" in error_str.lower():
        return (
            "🌐 Database Connection Issue: Unable to connect to the database. "
            "Please check your connection and try again."
        )

    # Default fallback - return original error but more user-friendly
    return f"💾 Database Error: {error_str}"
