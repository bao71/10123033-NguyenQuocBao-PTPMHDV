"""Call fixed SQL Server stored procedures with positional bound parameters."""

import re

import pyodbc


def call(connection: pyodbc.Connection, name: str, *parameters: object) -> pyodbc.Cursor:
    if not re.fullmatch(r"clinic_[a-z_]+", name):
        raise ValueError("Invalid stored procedure name")
    placeholders = ", ".join("?" for _ in parameters)
    statement = f"EXEC dbo.{name}" + (f" {placeholders}" if placeholders else "")
    return connection.execute(statement, *parameters)
