import sys
from typing import Literal

import streamlit as st
from loguru import logger
from streamlit import session_state as ss


def log(
    action: Literal["CREATE", "UPDATE", "DELETE"],
    table: str,
    row,
    success: bool = True,
):
    message = "| Action={} | Table={} | Row={}"
    if success:
        logger.info(message, action, table, str(row))
    else:
        logger.error(message, action, table, str(row))


def set_logging(disable_log: bool):
    if disable_log:
        logger.disable("streamlit_sql")
        return

    logger.enable("streamlit_sql")
    if not logger._core.handlers:  # pyright: ignore
        logger.add(sys.stderr, level="INFO")


def set_state(key: str, value):
    if key not in ss:
        ss[key] = value


@st.cache_data
def get_pretty_name(name: str):
    pretty_name = " ".join(name.split("_")).title()
    return pretty_name


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
        return ("⚠️ Database Configuration Issue: This table appears to use auto-generated IDs, "
               "but the database is not properly configured for ID generation. "
               "Please ensure your database table has auto-increment/sequence enabled for the ID column, "
               "or exclude the ID field from your create schema.")
    
    # Handle unique constraint violations
    elif "UNIQUE constraint failed" in error_str or "duplicate key" in error_str.lower():
        return ("❌ Duplicate Entry: A record with these values already exists. "
               "Please check for duplicate entries and try again.")
    
    # Handle foreign key constraint violations
    elif "FOREIGN KEY constraint failed" in error_str or "foreign key" in error_str.lower():
        return ("🔗 Invalid Reference: One or more referenced records don't exist. "
               "Please ensure all referenced data is valid and try again.")
    
    # Handle NOT NULL constraint violations
    elif "NOT NULL constraint failed" in error_str or "cannot be null" in error_str.lower():
        return ("📝 Missing Required Fields: Some required fields are missing. "
               "Please fill in all required fields and try again.")
    
    # Handle connection/timeout errors
    elif "connection" in error_str.lower() or "timeout" in error_str.lower():
        return ("🌐 Database Connection Issue: Unable to connect to the database. "
               "Please check your connection and try again.")
    
    # Default fallback - return original error but more user-friendly
    else:
        return f"💾 Database Error: {error_str}"


if __name__ == "__main__":
    set_logging(False)
    log(action="CREATE", table="tableA", row="rowabc")
    log(action="UPDATE", table="tableB", row="xyzw", success=False)
