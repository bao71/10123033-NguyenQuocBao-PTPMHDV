from collections.abc import Generator

import pyodbc

from Core.config import get_settings
from DAL.procedures import call

pyodbc.pooling = True


def connect() -> pyodbc.Connection:
    settings = get_settings()
    return pyodbc.connect(
        settings.database_connection_string,
        autocommit=False,
        timeout=settings.db_connection_timeout_seconds,
    )


def get_db() -> Generator[pyodbc.Connection, None, None]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def database_is_ready() -> bool:
    try:
        with connect() as connection:
            cursor = call(connection, "clinic_health_ready")
            return cursor.fetchone().ready == 1
    except pyodbc.Error:
        return False
