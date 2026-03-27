# Nexus Intelligence

Enterprise-grade Relational Database Intelligence Agent for hackathon execution.

This application analyzes multi-table relational data from SQLite databases or CSV bundles and automatically generates:

- Schema understanding (tables, columns, candidate keys)
- Relationship mapping and ER structure
- Data quality metrics (nulls, completeness, consistency, temporal regularity bonus/penalty)
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
- Temporal regularity bonus/penalty for time dimensions (relative cadence, not absolute recency)
- Duplicate identifier checks
- Rule-based issue detection
- Quality formula: base score is `50% completeness + 50% consistency`, then temporal regularity adjusts the score up or down.

1. Data Dictionary Agent

- Column-level semantic labeling
- Data quality notes
- Sample values and generated descriptions

1. Semantic Layer (Metadata-Driven Intelligence)

- Versioned semantic config in `semantic_layer.json`
- Table-to-entity mapping (customer, order, product, etc.)
- Role-aware column classification (`business_key`, `foreign_key`, `measure`, `event_time`, `status`, `pii`)
- Semantic constraints and metric checks
- Mapping suggestions with confidence and source provenance

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

## Environment Variables (Optional but Recommended)

All configuration can be set via **environment variables** (which take precedence over secrets files):

### Backend (Python)
```bash
# Ollama
export OLLAMA_ENDPOINT=http://localhost:11434
export OLLAMA_API_KEY=         # optional

# Firebase (Agent login)
export FIREBASE_API_KEY=your-api-key
export FIREBASE_AUTH_DOMAIN=your-domain
export FIREBASE_PROJECT_ID=your-project
export FIREBASE_STORAGE_BUCKET=your-bucket
export AGENT_DEFAULT_EMAIL=your@email.com
```

### Frontend (React)
```bash
# In nexus-ui/.env.local (create from .env.example)
VITE_API_BASE=http://localhost:8000/api
```

For **Streamlit secrets** (alternative to env vars):
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
- Fill in values as needed
- `.streamlit/secrets.toml` is **already in .gitignore** (don't commit it)

## Run

**Option 1: Streamlit UI (Recommended for development)**
```bash
streamlit run app.py
# Opens at http://localhost:8501
```

**Option 2: Full Stack (Streamlit + React UI + Backend API)**
```bash
# Terminal 1: Backend API server
python api.py
# API runs on http://localhost:8000

# Terminal 2: React UI
cd nexus-ui
npm run dev
# UI runs on http://localhost:5173

# Terminal 3: Streamlit
streamlit run app.py
# Streamlit runs on http://localhost:8501
```

## Semantic Layer Configuration

The project now ships with a semantic metadata contract at `semantic_layer.json`.

- Edit this file to define domain entities, role synonyms, and strict column overrides.
- The analysis pipeline automatically applies this layer during key inference, relationship scoring, profiling, and dictionary generation.
- Streamlit includes a **Semantic Layer** tab to review confidence, entity mappings, constraint violations, and suggested mappings.

API endpoints for semantic lifecycle:

- `GET /api/semantic/config`
- `PUT /api/semantic/config`
- `POST /api/semantic/validate`
- `GET /api/semantic/suggest`
- `GET /api/semantic/ambiguities`
- `POST /api/semantic/overrides/apply`
- `GET /api/semantic/drift`

Examiner-killer semantic capabilities now included:

- **One-click auto-lock** of high-confidence semantic suggestions into `column_overrides`
- **Run-to-run semantic drift** tracking (confidence / violations / ambiguities deltas)
- **Confidence uplift report** comparing baseline relationship inference vs semantic-enhanced inference

Supported semantic constraint types in `semantic_layer.json`:

- `role_presence`
- `role_null_threshold`
- `column_regex`
- `allowed_values`
- `column_range`

**Option 3: React UI Only (requires backend API)**
```bash
# Terminal 1: Backend API
python api.py

# Terminal 2: React UI
cd nexus-ui
npm run dev -- --host 0.0.0.0 --port 5173
# Accessible from other machines on the network
```

## Firebase Configuration (Optional)

The Streamlit prototype reads Firebase runtime config from environment variables or Streamlit secrets (instead of entering these values in the UI).

Set these via environment variables or `.streamlit/secrets.toml`:

- `FIREBASE_API_KEY`
- `FIREBASE_AUTH_DOMAIN`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_STORAGE_BUCKET`
- `AGENT_DEFAULT_EMAIL` (optional)

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
├── app.py                 # Main Nexus Intelligence application
├── requirements.txt       # Runtime dependencies
├── dbi_audit_ledger.json  # Generated immutable analysis snapshots
└── SY_SEM_3_DBMS_CP_NoSQL2SQL/  # Prior project assets (optional reuse)
```
