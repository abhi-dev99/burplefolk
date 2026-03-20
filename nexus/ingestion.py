import io
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd

from .models import DBConnectionConfig
from .schema import sanitize_name


def csv_ingest(uploaded_files: List, profile_row_limit: int) -> Tuple[Dict[str, pd.DataFrame], Dict[str, int]]:
    tables: Dict[str, pd.DataFrame] = {}
    row_counts: Dict[str, int] = {}

    for uploaded in uploaded_files:
        raw = uploaded.getvalue()
        name = sanitize_name(Path(uploaded.name).stem)
        newline_count = raw.count(b"\n")
        row_counts[name] = max(0, newline_count - 1)
        sampled = pd.read_csv(io.BytesIO(raw), nrows=profile_row_limit)
        tables[name] = sampled

    return tables, row_counts


def sqlite_ingest(file_bytes: bytes, profile_row_limit: int) -> Tuple[Dict[str, pd.DataFrame], Dict[str, int], List[Dict]]:
    tables: Dict[str, pd.DataFrame] = {}
    row_counts: Dict[str, int] = {}
    explicit_relationships: List[Dict] = []

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        conn = sqlite3.connect(temp_path)
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        table_names = [r[0] for r in table_rows]

        for table in table_names:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            row_counts[table] = int(count)
            sampled = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT {profile_row_limit}', conn)
            tables[table] = sampled

            fk_rows = conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
            for fk in fk_rows:
                explicit_relationships.append(
                    {
                        "child_table": table,
                        "child_column": fk[3],
                        "parent_table": fk[2],
                        "parent_column": fk[4],
                        "relation_type": "many-to-one",
                        "confidence": 1.0,
                    }
                )
    finally:
        try:
            conn.close()
        except Exception:
            pass
        os.unlink(temp_path)

    return tables, row_counts, explicit_relationships


def build_db_url(cfg: DBConnectionConfig) -> str:
    safe_user = quote_plus(cfg.username)
    safe_pwd = quote_plus(cfg.password)
    safe_host = cfg.host.strip()
    safe_db = quote_plus(cfg.database)

    if cfg.db_type == "mysql":
        return f"mysql+pymysql://{safe_user}:{safe_pwd}@{safe_host}:{cfg.port}/{safe_db}"
    if cfg.db_type == "postgres":
        return f"postgresql+psycopg2://{safe_user}:{safe_pwd}@{safe_host}:{cfg.port}/{safe_db}"
    if cfg.db_type == "sqlserver":
        safe_driver = quote_plus(cfg.driver)
        return (
            f"mssql+pyodbc://{safe_user}:{safe_pwd}@{safe_host}:{cfg.port}/{safe_db}"
            f"?driver={safe_driver}&TrustServerCertificate=yes"
        )
    raise ValueError(f"Unsupported db_type: {cfg.db_type}")


def format_db_connection_error(exc: Exception, cfg: Optional[DBConnectionConfig] = None) -> str:
    raw_error = str(exc)
    error_text = raw_error.lower()
    hints: List[str] = []

    if (
        "access denied" in error_text
        or "authentication failed" in error_text
        or "login failed" in error_text
        or "password authentication failed" in error_text
    ):
        hints.append("Credentials were rejected by the database server.")
        hints.append("Verify username/password and confirm this user has access to the selected database.")
        if cfg and cfg.db_type == "mysql" and cfg.host.strip().lower() in {"localhost", "127.0.0.1"}:
            hints.append("For local XAMPP MariaDB, try user 'root' with the password configured in XAMPP.")
    elif "unknown database" in error_text or ("does not exist" in error_text and "database" in error_text):
        hints.append("The provided database name was not found.")
        hints.append("Check the exact database name and retry.")
    elif (
        "can\'t connect" in error_text
        or "could not connect" in error_text
        or "connection refused" in error_text
        or "timed out" in error_text
        or "timeout" in error_text
    ):
        hints.append("The database server is unreachable.")
        hints.append("Confirm host/port and ensure the database service is running.")
    elif "driver" in error_text and (
        "not found" in error_text or "can\'t open lib" in error_text or "data source name not found" in error_text
    ):
        hints.append("A required database driver appears to be missing.")
        hints.append("Install pymysql (MySQL), psycopg2-binary (PostgreSQL), or pyodbc + ODBC driver (SQL Server).")
    else:
        hints.append("Review the provider error below for exact details.")

    if cfg:
        hints.append(f"Target: {cfg.db_type}://{cfg.host}:{cfg.port}/{cfg.database}")

    return "Database connection failed.\n" + "\n".join(f"- {h}" for h in hints) + f"\n\nRaw error: {raw_error}"


def database_ingest(cfg: DBConnectionConfig, profile_row_limit: int) -> Tuple[Dict[str, pd.DataFrame], Dict[str, int], List[Dict]]:
    try:
        import importlib

        sqlalchemy = importlib.import_module("sqlalchemy")
        MetaData = sqlalchemy.MetaData
        Table = sqlalchemy.Table
        create_engine = sqlalchemy.create_engine
        func = sqlalchemy.func
        inspect = sqlalchemy.inspect
        select = sqlalchemy.select
    except ImportError as exc:
        raise RuntimeError(
            "Database connector support requires SQLAlchemy. Install with: pip install sqlalchemy"
        ) from exc

    url = build_db_url(cfg)
    try:
        engine = create_engine(url, pool_pre_ping=True)
        inspector = inspect(engine)
    except Exception as exc:
        raise RuntimeError(format_db_connection_error(exc, cfg)) from exc

    tables: Dict[str, pd.DataFrame] = {}
    row_counts: Dict[str, int] = {}
    explicit_relationships: List[Dict] = []

    try:
        table_names = inspector.get_table_names()
        with engine.connect() as conn:
            for table_name in table_names:
                metadata = MetaData()
                table = Table(table_name, metadata, autoload_with=engine)

                count_stmt = select(func.count()).select_from(table)
                row_counts[table_name] = int(conn.execute(count_stmt).scalar_one())

                sample_stmt = select(table).limit(profile_row_limit)
                tables[table_name] = pd.read_sql(sample_stmt, conn)

                for fk in inspector.get_foreign_keys(table_name):
                    child_cols = fk.get("constrained_columns") or []
                    parent_cols = fk.get("referred_columns") or []
                    if not child_cols or not parent_cols:
                        continue
                    explicit_relationships.append(
                        {
                            "child_table": table_name,
                            "child_column": child_cols[0],
                            "parent_table": fk.get("referred_table", ""),
                            "parent_column": parent_cols[0],
                            "relation_type": "many-to-one",
                            "confidence": 1.0,
                        }
                    )
    except Exception as exc:
        raise RuntimeError(format_db_connection_error(exc, cfg)) from exc
    finally:
        try:
            engine.dispose()
        except Exception:
            pass

    return tables, row_counts, explicit_relationships


def test_database_connection(cfg: DBConnectionConfig) -> Tuple[bool, str]:
    try:
        import importlib

        sqlalchemy = importlib.import_module("sqlalchemy")
        create_engine = sqlalchemy.create_engine
        inspect = sqlalchemy.inspect
        text = sqlalchemy.text
    except ImportError:
        return False, "SQLAlchemy is not installed. Install with: pip install sqlalchemy"

    engine = None
    try:
        engine = create_engine(build_db_url(cfg), pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        table_count = len(inspect(engine).get_table_names())
        return True, f"Connection succeeded. Visible tables: {table_count}"
    except Exception as exc:
        return False, format_db_connection_error(exc, cfg)
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
