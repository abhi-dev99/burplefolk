# Nexus Intelligence Fabric

Enterprise-grade Relational Database Intelligence Agent for hackathon execution.

This application analyzes multi-table relational data from SQLite, CSV bundles, or direct enterprise DB connections and automatically generates:

- Schema understanding (tables, columns, candidate keys)
- Relationship mapping and ER structure
- Data quality metrics (nulls, completeness, freshness, consistency)
- AI-assisted business context summaries
- Human-readable data dictionaries
- Exportable governance artifacts with immutable audit hashes

## Why This Is Built To Win

- Complete end-to-end workflow: ingestion to exports
- Explainable outputs with confidence scores
- Production-style UX and governance trail
- Scales with configurable sampling for large datasets
- Fully functional even without external cloud dependencies

## Core Capabilities

1. Ingestion Modes

- SQLite upload (`.db`, `.sqlite`, `.sqlite3`)
- Multi-table CSV bundle upload
- Direct database connections: MySQL, PostgreSQL, SQL Server

1. Schema Intelligence

- Candidate primary key detection
- Relationship inference with confidence scores
- Explicit FK parsing for SQLite via `PRAGMA foreign_key_list`

1. Data Quality Engine

- Completeness scoring
- Consistency scoring
- Freshness scoring for time dimensions
- Duplicate identifier checks
- Rule-based issue detection

1. Data Dictionary Agent

- Column-level semantic labeling
- Data quality notes
- Sample values and generated descriptions

1. AI Analyst Layer (Optional)

- Local LLM integration using Ollama
- Executive brief generation for leadership and judges

1. Governance and Exports

- JSON analysis export
- CSV relationship export
- Mermaid ER export
- Immutable audit ledger with SHA-256 snapshots

## Technology Stack

- Python 3.10+
- Streamlit
- Pandas + NumPy
- PyVis (interactive ER graph)
- SQLite (`sqlite3` standard library)
- Requests (for Ollama integration)
- SQLAlchemy (for direct DB connectivity)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Full CLI Access

All core features are available via terminal using `nexus_cli.py`:

1. List Ollama models

```bash
python nexus_cli.py models
```

1. Analyze CSV bundle and export all artifacts

```bash
python nexus_cli.py analyze --source csv --csv data/customers.csv data/orders.csv data/payments.csv --out-dir outputs/cli_run --ai-brief --commit-audit --actor TeamName
```

1. Analyze SQLite database

```bash
python nexus_cli.py analyze --source sqlite --sqlite data/olist.db --out-dir outputs/sqlite_run --ai-brief
```

1. Analyze enterprise DB directly (MySQL/PostgreSQL/SQL Server)

```bash
python nexus_cli.py analyze --source db --db-type mysql --host localhost --port 3306 --database mydb --username root --password secret --out-dir outputs/mysql_run --ai-brief
```

For SQL Server, set `--db-type sqlserver` and use ODBC driver if needed:

```bash
python nexus_cli.py analyze --source db --db-type sqlserver --host localhost --port 1433 --database mydb --username sa --password secret --driver "ODBC Driver 17 for SQL Server" --out-dir outputs/sqlserver_run
```

CLI exports include:

- `nexus_analysis.json`
- `data_dictionary.csv`
- `relationships.csv`
- `quality_report.csv`
- `er_diagram.mmd`
- `er_graph.html`
- `ai_brief.txt` (when `--ai-brief` is used)

For load testing limits:

```bash
python benchmark_limits.py --rows 300000 --limit 25000
```

## Generate Validation Datasets (with intentional issues)

Create clean and broken datasets to verify if the platform catches problems:

```bash
python generate_test_datasets.py --out outputs/test_scenarios --rows 60000
```

Generated scenarios:

- `clean_bundle`: mostly healthy relational data
- `quality_issues_bundle`: high nulls, duplicates, mixed data types, stale timestamps
- `schema_issues_bundle`: orphan references, noisy/unlinked table, key mismatch patterns
- `sqlite_demo/enterprise_demo.db`: SQLite relational DB for DB-file ingestion testing

## Score and ER Diagram Meaning

In the frontend, open **"How scoring works (read this first)"** for details.

- Data Quality Score formula: `45% completeness + 35% consistency + 20% freshness`
- Relationship Confidence:
	- `1.0` for explicit foreign keys from metadata
	- inferred confidence for overlap-based key matching
- ER Diagram:
	- node size represents relative volume
	- node color represents quality band
	- edges represent candidate or explicit relationships

## Enterprise Connector Testing Notes

- MySQL: requires `pymysql`
- PostgreSQL: requires `psycopg2-binary`
- SQL Server: requires `pyodbc` + compatible ODBC driver installed

## Optional: Local AI Copilot (Free)

Install Ollama and run a local model:

```bash
ollama pull llama3.1
ollama run llama3.1
```

Then keep endpoint as `http://localhost:11434` in the sidebar.

## Recommended Demo Flow

1. Upload Olist-style SQLite or multiple CSV tables.
2. Show Overview metrics and quality risk concentration.
3. Open ER Graph and explain confidence-based relationships.
4. Open Data Quality tab and show rule-triggered issues.
5. Open Data Dictionary tab and download CSV/JSON.
6. Generate AI Executive Brief.
7. Commit analysis snapshot and show immutable hash in audit ledger.

## Notes for Hackathon Rule Compliance

- Use only open datasets with proper attribution.
- Credit all external tools used for assistance.
- Build and iterate during official hackathon hours.

## Project Structure

```text
.
├── app.py                 # Main Nexus Intelligence Fabric application
├── requirements.txt       # Runtime dependencies
├── dbi_audit_ledger.json  # Generated immutable analysis snapshots
└── SY_SEM_3_DBMS_CP_NoSQL2SQL/  # Prior project assets (optional reuse)
```
