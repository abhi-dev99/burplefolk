# Nexus Intelligence Fabric

Enterprise-grade Relational Database Intelligence Agent for hackathon execution.

This application analyzes multi-table relational data from SQLite databases or CSV bundles and automatically generates:

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
