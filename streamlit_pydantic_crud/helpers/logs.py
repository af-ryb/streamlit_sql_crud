"""CRUD action logging through loguru, switchable per SqlUi."""

from typing import Literal

from loguru import logger


def log(
    action: Literal["CREATE", "UPDATE", "DELETE"],
    table: str,
    row: object,
    success: bool = True,
) -> None:
    """Log a CRUD action on `table`: info on success, error otherwise."""
    message = "| Action={} | Table={} | Row={}"
    if success:
        logger.info(message, action, table, str(row))
    else:
        logger.error(message, action, table, str(row))


def set_logging(disable_log: bool) -> None:
    """Disable or re-enable every log record of this package."""
    if disable_log:
        logger.disable("streamlit_pydantic_crud")
        return

    logger.enable("streamlit_pydantic_crud")
