# Nexus Intelligence Fabric - Agent Handoff Context

Last updated: 2026-03-16
Workspace root: `c:\Users\abhi\burplefolk`
Primary app entrypoint: `app.py`

## 1) Executive Summary

The project has been transformed from a Streamlit prototype into a multi-mode Relational Database Intelligence platform with:

- CSV bundle analysis
- SQLite file analysis
- Direct enterprise DB connection support scaffold (MySQL, PostgreSQL, SQL Server)
- Relationship inference with confidence scoring
- Data quality scoring with explainability
- Data dictionary generation
- Ollama-based AI brief generation (local model)
- CLI parity for core workflows
- Synthetic test dataset generation with intentional data and schema defects

The application is functional for CSV/SQLite and CLI workflows. Enterprise live DB mode is implemented in code but needs environment-specific driver setup and live connection tests per target DB.

---

## 2) Current Code Surface (Important Files)

- `app.py`
  - Main Streamlit app
  - Ingestion modes: SQLite, CSV Bundle, DB Connection
  - Quality + relationship analysis
  - UI tabs for Overview/Schema/ER/Quality/Dictionary/AI/Exports
  - Progress indicator for processing stages
  - In-UI metric explanation panel

- `nexus_cli.py`
  - Terminal-first command interface
  - `models` command for Ollama model discovery
  - `analyze` command for CSV/SQLite/DB connection modes
  - Artifact export + optional AI brief + optional audit commit

- `generate_test_datasets.py`
  - Generates test scenarios:
    - clean bundle
    - quality issues bundle
    - schema issues bundle
    - SQLite demo DB

- `benchmark_limits.py`
  - Synthetic load benchmark utility for scaling tests

- `requirements.txt`
  - Includes core deps + `sqlalchemy`

- `README.md`
  - Updated with CLI + DB + test generation workflows

---

## 3) Feature Status Matrix

## COMPLETELY IMPLEMENTED

1. CSV Bundle ingestion in UI and CLI
- Status: complete
- Verified: yes
- Files: `app.py`, `nexus_cli.py`

2. SQLite ingestion in UI and CLI
- Status: complete
- Verified: yes
- Files: `app.py`, `nexus_cli.py`, generated SQLite in `generate_test_datasets.py`

3. Data quality scoring pipeline
- Formula currently used:
  - 45% completeness
  - 35% consistency
  - 20% freshness
- Status: complete
- Verified: yes
- Files: `app.py` (`profile_table`)

4. Relationship inference + confidence
- Explicit FK confidence set to `1.0`
- Inferred relationships confidence from overlap ratio
- Status: complete
- Verified: yes
- Files: `app.py` (`infer_foreign_keys`, merge logic)

5. ER graph rendering + Mermaid export
- Status: complete
- Verified: yes
- Files: `app.py`, `nexus_cli.py`

6. Data dictionary generation
- Status: complete
- Verified: yes
- Files: `app.py` (`build_dictionary`)

7. Ollama integration (model discovery + generation)
- Status: complete for local Ollama
- Verified: yes (`llama3:latest` tested)
- Files: `app.py`, `nexus_cli.py`

8. CLI access to core features
- Models listing, analysis, AI brief, artifacts, audit commit
- Status: complete
- Verified: yes
- Files: `nexus_cli.py`

9. Fault-injected dataset generation
- Status: complete
- Verified: yes
- Files: `generate_test_datasets.py`

10. Crash fix for empty relationship table (`KeyError: 'confidence'`)
- Status: complete
- Verified: yes
- Files: `app.py` relation tab safety

11. Processing progress indicator in frontend
- Status: complete (stage-level progress)
- Verified: yes
- Files: `app.py` (`progress_callback` plumbing)

12. Score/explanation docs in frontend
- Status: complete
- Verified: yes
- Files: `app.py` (`render_metric_explanations`)

## MID-IMPLEMENTATION / PARTIALLY VERIFIED

1. Enterprise DB direct connections (MySQL/PostgreSQL/SQL Server)
- Status: implemented in code paths + CLI flags
- Verification status: partial
  - Code-level compile/test passed
  - No live E2E against running MySQL/Postgres/SQL Server instances yet in this workspace
- Why partial:
  - Requires DB servers and client drivers
  - Requires credentials/network access
- Files: `app.py` (`DBConnectionConfig`, `build_db_url`, `database_ingest`), `nexus_cli.py`

2. SQL Server connector reliability across environments
- Status: partial
- Note:
  - Uses `pyodbc` style URL and driver name input
  - Needs actual ODBC driver install and runtime validation

3. Streamlit runtime UX polish
- Status: partial
- Notes:
  - Core UX works
  - Further polish requested by user (less scattered flow, clearer onboarding walkthrough)

## TO COME (PLANNED IN NEXT COUPLE OF UPDATES)

### Update 1 (Stability + Enterprise Readiness)

1. Add explicit "Test Connection" button in UI for DB mode
- Validate host/port/db/auth before full run
- Show actionable diagnostics in UI

2. Add optional driver-dependency preflight checks
- MySQL: `pymysql`
- PostgreSQL: `psycopg2-binary`
- SQL Server: `pyodbc` + ODBC driver

3. Improve relationship inference guardrails
- Add configurable confidence threshold in UI/CLI
- Add classification labels (high/medium/low confidence)

4. Add per-table progress details
- Show currently processing table name and stage

### Update 2 (Usability + Governance)

1. Guided onboarding panel in UI
- "What this app does" + "How to read outputs"
- Reduce cognitive load for first-time users

2. Quality score explainability card per table
- Decompose contributions (completeness/consistency/freshness)
- Show weighted impact graph

3. Validation report summary page
- Aggregate top anomalies
- Suggested remediation actions per issue type

4. Auto-generated run metadata bundle
- Environment, run parameters, durations, warnings
- Useful for hackathon judging and enterprise audit trail

---

## 4) Known Issues / Risks / Notes

1. Streamlit exit code confusion in terminal
- `streamlit run app.py` can show exit code `1` in captured commands when process is interrupted/timeboxed.
- This is not always an app crash.

2. DB connectors need environment setup
- `sqlalchemy` is installed.
- Additional DB-specific drivers may be required per environment.

3. AI brief quality depends on local model
- Ollama model output quality and structure may vary.
- Currently validated with `llama3:latest`.

4. Some generated quality issues may not always surface as severe
- Detection depends on sample size and current scoring rules.
- Consider adding stricter rule thresholds for demo-heavy anomaly visibility.

---

## 5) Verified Run Evidence (Recent)

1. Quality-issue dataset run
- Command used via CLI
- Outcome:
  - source_type: CSV Bundle
  - tables: 3
  - relationships: 5
  - avg_quality_score: ~82.53
  - artifacts created in `outputs/quality_issues_run_v2`

2. Schema-issue dataset run
- Outcome:
  - source_type: CSV Bundle
  - tables: 4
  - relationships: 4
  - avg_quality_score: ~83.75

3. SQLite demo run
- Outcome:
  - source_type: SQLite
  - tables: 3
  - relationships: 5
  - avg_quality_score: ~85.0

4. Benchmark sample
- 300k rows/table scenario tested with benchmark utility
- Analysis completed successfully in single-digit to low double-digit seconds depending on run conditions

---

## 6) Operational Runbook (For Next Agent)

## Setup

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run app

```powershell
streamlit run app.py
```

## Generate test datasets

```powershell
python generate_test_datasets.py --out outputs/test_scenarios --rows 60000
```

## CLI analyze (CSV)

```powershell
python nexus_cli.py analyze --source csv --csv outputs/test_scenarios/quality_issues_bundle/customers.csv outputs/test_scenarios/quality_issues_bundle/orders.csv outputs/test_scenarios/quality_issues_bundle/payments.csv --out-dir outputs/quality_issues_run --ai-brief
```

## CLI analyze (SQLite)

```powershell
python nexus_cli.py analyze --source sqlite --sqlite outputs/test_scenarios/sqlite_demo/enterprise_demo.db --out-dir outputs/sqlite_demo_run
```

## CLI analyze (DB connection)

```powershell
python nexus_cli.py analyze --source db --db-type mysql --host localhost --port 3306 --database mydb --username root --password secret --out-dir outputs/mysql_run
```

---

## 7) Terminal Discipline Guidance (Important)

When working with this project, keep server and tests isolated:

1. Keep Streamlit server in one terminal.
2. Run CLI/tests in separate terminal sessions.
3. Do not reuse the server terminal for heavy test scripts.
4. Prefer background terminal sessions for long-running tasks.

This prevents accidental interruption/crash of the active UI session.

---

## 8) Suggested Immediate Priorities for Next Agent

1. Execute live connection tests against MySQL/PostgreSQL/SQL Server (if infra available).
2. Implement DB "Test Connection" button + structured diagnostics in UI.
3. Add confidence-threshold controls and per-table progress telemetry.
4. Ship an onboarding tutorial section to reduce perceived UI scatter.
5. Produce a capacity report artifact for judging (`rows`, `tables`, `analysis_sec`, `quality_score`).

---

## 9) Completion Definition for "Enterprise-Ready" Claim

The next agent should mark enterprise readiness only after:

1. Live E2E verified on at least one managed or local MySQL/PostgreSQL/SQL Server target.
2. Connection-failure diagnostics are user-friendly and actionable.
3. UI clearly explains every score and relationship confidence with examples.
4. Benchmark report generated and attached for large-volume scenarios.
5. Export package includes analysis JSON, dictionary CSV, relationship CSV, quality report, ER Mermaid, ER HTML, and optional AI brief.
