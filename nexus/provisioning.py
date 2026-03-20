from __future__ import annotations

import importlib
from typing import Dict, List, Tuple

import pandas as pd

from .ingestion import build_db_url
from .models import DBConnectionConfig


def _normalize_mysql_error(exc: Exception) -> str:
    raw = str(exc)
    lower = raw.lower()

    if "cryptography" in lower and ("sha256_password" in lower or "caching_sha2_password" in lower):
        return (
            "MySQL authentication requires the `cryptography` package for sha256/caching_sha2. "
            "Install with: pip install cryptography"
        )
    if "access denied" in lower or "authentication" in lower or "login" in lower:
        return "Authentication failed. Verify MySQL username/password and host access permissions."
    if "can't connect" in lower or "connection refused" in lower or "timed out" in lower:
        return "Unable to reach MySQL server. Verify host/port and ensure MySQL is running."
    if "unknown database" in lower:
        return "Target database does not exist (or cannot be accessed)."
    return f"MySQL error: {raw}"


def test_mysql_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str = "information_schema",
) -> Tuple[bool, str]:
    try:
        sqlalchemy = importlib.import_module("sqlalchemy")
        create_engine = sqlalchemy.create_engine
        text = sqlalchemy.text
    except ImportError:
        return False, "SQLAlchemy is not installed. Install with: pip install sqlalchemy"

    db_name = (database or "information_schema").strip() or "information_schema"
    cfg = DBConnectionConfig(
        db_type="mysql",
        host=host.strip(),
        port=int(port),
        database=db_name,
        username=username,
        password=password,
    )
    engine = None
    try:
        engine = create_engine(build_db_url(cfg), pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, f"Connection established to MySQL at {host}:{port} as {username}."
    except Exception as exc:
        return False, _normalize_mysql_error(exc)
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass


def _mysql_type_from_dictionary(dtype: str) -> str:
    value = (dtype or "").strip().lower()
    if any(token in value for token in ["bigint"]):
        return "BIGINT"
    if any(token in value for token in ["int", "int64", "int32"]):
        return "INT"
    if any(token in value for token in ["decimal", "numeric"]):
        return "DECIMAL(18,4)"
    if any(token in value for token in ["float", "double", "real"]):
        return "DOUBLE"
    if "bool" in value:
        return "TINYINT(1)"
    if any(token in value for token in ["date", "time", "timestamp", "datetime"]):
        return "DATETIME"
    if "text" in value:
        return "TEXT"
    return "VARCHAR(255)"


def _quote_identifier(identifier: str) -> str:
    return "`" + str(identifier).replace("`", "") + "`"


def build_mysql_ddl_from_dictionary(dictionary_df: pd.DataFrame) -> List[str]:
    if dictionary_df.empty:
        return []

    ordered = dictionary_df.copy()
    if "_row_id" in ordered.columns:
        ordered = ordered.sort_values("_row_id")

    statements: List[str] = []
    for table_name, group in ordered.groupby("table", sort=False):
        columns_sql: List[str] = []
        pk_columns: List[str] = []

        for _, row in group.iterrows():
            column_name = str(row.get("column", "")).strip()
            if not column_name:
                continue

            mysql_type = _mysql_type_from_dictionary(str(row.get("data_type", "")))
            is_pk = bool(row.get("is_primary_candidate", False))
            null_sql = "NOT NULL" if is_pk else "NULL"
            columns_sql.append(f"{_quote_identifier(column_name)} {mysql_type} {null_sql}")

            if is_pk:
                pk_columns.append(column_name)

        if not columns_sql:
            continue

        if pk_columns:
            quoted_pk = ", ".join(_quote_identifier(col) for col in pk_columns)
            columns_sql.append(f"PRIMARY KEY ({quoted_pk})")

        quoted_table = _quote_identifier(table_name)
        stmt = (
            f"CREATE TABLE IF NOT EXISTS {quoted_table} (\n  "
            + ",\n  ".join(columns_sql)
            + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        )
        statements.append(stmt)

    return statements


def provision_mysql_from_dictionary(
    dictionary_df: pd.DataFrame,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
) -> Tuple[bool, str, List[str]]:
    if dictionary_df.empty:
        return False, "Data dictionary is empty; no schema can be created.", []

    if not database.strip():
        return False, "Database name is required.", []

    try:
        sqlalchemy = importlib.import_module("sqlalchemy")
        create_engine = sqlalchemy.create_engine
    except ImportError:
        return False, "SQLAlchemy is not installed. Install with: pip install sqlalchemy", []

    ddl_statements = build_mysql_ddl_from_dictionary(dictionary_df)
    if not ddl_statements:
        return False, "No DDL statements were generated from the dictionary.", []

    safe_db = database.strip().replace("`", "")
    server_engine = None
    target_engine = None

    try:
        server_cfg = DBConnectionConfig(
            db_type="mysql",
            host=host.strip(),
            port=int(port),
            database="information_schema",
            username=username,
            password=password,
        )
        server_engine = create_engine(build_db_url(server_cfg), pool_pre_ping=True, isolation_level="AUTOCOMMIT")
        with server_engine.connect() as conn:
            conn.exec_driver_sql(
                f"CREATE DATABASE IF NOT EXISTS `{safe_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

        target_cfg = DBConnectionConfig(
            db_type="mysql",
            host=host.strip(),
            port=int(port),
            database=safe_db,
            username=username,
            password=password,
        )
        target_engine = create_engine(build_db_url(target_cfg), pool_pre_ping=True)
        with target_engine.begin() as conn:
            for stmt in ddl_statements:
                conn.exec_driver_sql(stmt)

        return True, f"MySQL schema provisioned successfully in database '{safe_db}'.", ddl_statements
    except Exception as exc:
        return False, _normalize_mysql_error(exc), ddl_statements
    finally:
        if server_engine is not None:
            try:
                server_engine.dispose()
            except Exception:
                pass
        if target_engine is not None:
            try:
                target_engine.dispose()
            except Exception:
                pass
