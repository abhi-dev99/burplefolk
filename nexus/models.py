from dataclasses import dataclass

APP_TITLE = "NEXUS INTELLIGENCE FABRIC"
AUDIT_FILE = "dbi_audit_ledger.json"


@dataclass
class DBConnectionConfig:
    db_type: str
    host: str
    port: int
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 17 for SQL Server"
