import hashlib
import io
import json
import math
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

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


def init_page() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
        :root {
            --bg: #08131f;
            --surface: #13283a;
            --surface-soft: #1d3449;
            --accent: #f6d365;
            --accent-2: #fda085;
            --text: #eaf1f8;
            --muted: #a4b6c7;
            --danger: #ff7b72;
            --ok: #7ee787;
        }
        .stApp {
            background:
                radial-gradient(1200px 500px at 10% 0%, rgba(253, 160, 133, 0.18), transparent),
                radial-gradient(900px 500px at 90% 10%, rgba(246, 211, 101, 0.22), transparent),
                linear-gradient(180deg, #091624, #08131f);
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
        }
        h1, h2, h3, h4 { color: var(--accent); letter-spacing: 0.4px; }
        .card {
            border: 1px solid rgba(246, 211, 101, 0.35);
            border-radius: 12px;
            background: linear-gradient(160deg, rgba(19,40,58,.85), rgba(14,29,44,.92));
            padding: 0.9rem 1rem;
            margin-bottom: 0.6rem;
        }
        .metric-big {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.1rem;
        }
        .muted { color: var(--muted); font-size: 0.9rem; }
        .pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.2rem 0.7rem;
            font-size: 0.82rem;
            border: 1px solid rgba(246, 211, 101, 0.45);
            background: rgba(246, 211, 101, 0.07);
            margin-right: 0.4rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(24, 46, 66, 0.8);
            border-radius: 8px;
            margin-right: 8px;
            border: 1px solid rgba(164,182,199,0.2);
        }
        .stTabs [aria-selected="true"] {
            border-color: rgba(246,211,101,.7);
            box-shadow: inset 0 0 0 1px rgba(246,211,101,.7);
        }
        .stDataFrame { border: 1px solid rgba(164,182,199,0.35); border-radius: 10px; }
        div[data-testid="stFileUploader"] {
            background: rgba(19,40,58,0.75);
            border: 1px dashed rgba(246, 211, 101, 0.45);
            border-radius: 12px;
            padding: 0.6rem;
        }
        .stButton > button {
            border-radius: 8px;
            border: 1px solid rgba(246, 211, 101, .6);
            background: linear-gradient(140deg, rgba(246, 211, 101, .18), rgba(253, 160, 133, .18));
            color: #fefbf2;
            font-weight: 600;
        }
        .stDownloadButton > button {
            border-radius: 8px;
            border: 1px solid rgba(164, 182, 199, .55);
            background: rgba(164,182,199,.11);
            color: #fefbf2;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned.lower() or "table"


def semantic_label(column_name: str) -> str:
    col = column_name.lower()
    if col.endswith("_id") or col == "id":
        return "identifier"
    if any(tok in col for tok in ["date", "time", "timestamp", "created", "updated"]):
        return "time dimension"
    if any(tok in col for tok in ["name", "title", "desc", "comment", "review", "text"]):
        return "descriptive text"
    if any(tok in col for tok in ["amount", "price", "cost", "revenue", "total", "value"]):
        return "financial metric"
    if any(tok in col for tok in ["status", "state", "type", "category", "segment"]):
        return "categorical attribute"
    if any(tok in col for tok in ["lat", "lng", "longitude", "latitude", "geo"]):
        return "geospatial attribute"
    return "general attribute"


def infer_primary_keys(df: pd.DataFrame) -> List[str]:
    keys: List[str] = []
    for col in df.columns:
        series = df[col]
        if series.isna().any():
            continue
        if series.nunique(dropna=True) == len(series):
            keys.append(col)
    if not keys and "id" in df.columns:
        keys.append("id")
    return keys[:3]


def infer_foreign_keys(tables: Dict[str, pd.DataFrame], pk_map: Dict[str, List[str]]) -> List[Dict]:
    relationships: List[Dict] = []
    pk_value_cache: Dict[Tuple[str, str], set] = {}
    for parent_table, pk_cols in pk_map.items():
        parent_df = tables[parent_table]
        for pk in pk_cols:
            values = set(parent_df[pk].dropna().astype(str).head(15000).tolist())
            pk_value_cache[(parent_table, pk)] = values

    for child_table, child_df in tables.items():
        for child_col in child_df.columns:
            child_lower = child_col.lower()
            if not (child_lower.endswith("_id") or child_lower in {"id", "user", "customer_id", "order_id"}):
                continue
            child_values = set(child_df[child_col].dropna().astype(str).head(15000).tolist())
            if not child_values:
                continue

            best = None
            best_score = 0.0
            for (parent_table, parent_col), parent_values in pk_value_cache.items():
                if parent_table == child_table:
                    continue
                overlap = len(child_values & parent_values)
                score = overlap / max(1, len(child_values))
                if score > best_score:
                    best_score = score
                    best = (parent_table, parent_col)

            if best and best_score >= 0.45:
                relationships.append(
                    {
                        "child_table": child_table,
                        "child_column": child_col,
                        "parent_table": best[0],
                        "parent_column": best[1],
                        "relation_type": "many-to-one",
                        "confidence": round(best_score, 3),
                    }
                )
    return relationships


def classify_values(series: pd.Series, sample_size: int = 3000) -> Dict[str, float]:
    sample = series.dropna().astype(str).head(sample_size)
    if sample.empty:
        return {"unknown": 1.0}

    counts = {"numeric": 0, "datetime": 0, "boolean": 0, "text": 0}
    for value in sample:
        lower = value.strip().lower()
        if lower in {"true", "false", "yes", "no", "0", "1"}:
            counts["boolean"] += 1
            continue

        try:
            float(value.replace(",", ""))
            counts["numeric"] += 1
            continue
        except ValueError:
            pass

        dt = pd.to_datetime(pd.Series([value]), errors="coerce")
        if not dt.isna().iloc[0]:
            counts["datetime"] += 1
        else:
            counts["text"] += 1

    total = sum(counts.values())
    return {k: round(v / total, 4) for k, v in counts.items() if total > 0}


def profile_table(
    table_name: str,
    df: pd.DataFrame,
    total_rows: int,
    pk_candidates: List[str],
) -> Dict:
    col_profiles: List[Dict] = []
    issues: List[str] = []
    completeness_values: List[float] = []
    consistency_values: List[float] = []
    freshness_values: List[float] = []

    for col in df.columns:
        series = df[col]
        non_null = int(series.notna().sum())
        null_count = int(series.isna().sum())
        null_ratio = (null_count / max(1, len(df))) * 100
        unique_ratio = (series.nunique(dropna=True) / max(1, non_null)) * 100 if non_null else 0
        type_distribution = classify_values(series)
        dominant_type = max(type_distribution, key=type_distribution.get)
        type_consistency = type_distribution[dominant_type]
        semantic = semantic_label(col)

        if null_ratio > 35:
            issues.append(f"{table_name}.{col} has high missingness ({null_ratio:.1f}%).")
        if semantic == "identifier" and unique_ratio < 70:
            issues.append(f"{table_name}.{col} appears identifier-like but has low uniqueness ({unique_ratio:.1f}%).")

        freshness_days = None
        if semantic == "time dimension":
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().any():
                latest = parsed.max()
                delta = datetime.now(timezone.utc).replace(tzinfo=None) - latest.to_pydatetime().replace(tzinfo=None)
                freshness_days = float(max(0.0, delta.total_seconds() / 86400.0))
                freshness_score = max(0.0, 1 - min(freshness_days, 365) / 365)
                freshness_values.append(freshness_score)

        completeness_values.append(1 - (null_ratio / 100.0))
        consistency_values.append(type_consistency)

        col_profiles.append(
            {
                "table": table_name,
                "column": col,
                "sample_dtype": str(series.dtype),
                "semantic_role": semantic,
                "null_percent": round(null_ratio, 2),
                "unique_percent": round(unique_ratio, 2),
                "dominant_value_type": dominant_type,
                "type_consistency": round(type_consistency, 3),
                "freshness_lag_days": round(freshness_days, 2) if freshness_days is not None else None,
                "sample_values": ", ".join(series.dropna().astype(str).head(3).tolist()),
            }
        )

    duplicate_pk_issues = 0
    for pk in pk_candidates:
        dupes = int(df[pk].duplicated().sum())
        if dupes > 0:
            duplicate_pk_issues += dupes
            issues.append(f"{table_name}.{pk} has {dupes} duplicate values in analyzed sample.")

    completeness_score = float(np.mean(completeness_values)) if completeness_values else 0.0
    consistency_score = float(np.mean(consistency_values)) if consistency_values else 0.0
    freshness_score = float(np.mean(freshness_values)) if freshness_values else 0.75
    quality_score = round((0.45 * completeness_score + 0.35 * consistency_score + 0.20 * freshness_score) * 100, 2)

    return {
        "table": table_name,
        "sample_rows": int(len(df)),
        "estimated_total_rows": int(total_rows),
        "column_count": int(len(df.columns)),
        "pk_candidates": pk_candidates,
        "duplicate_pk_records": duplicate_pk_issues,
        "quality_score": quality_score,
        "completeness_score": round(completeness_score * 100, 2),
        "consistency_score": round(consistency_score * 100, 2),
        "freshness_score": round(freshness_score * 100, 2),
        "issues": issues,
        "column_profiles": col_profiles,
    }


def compute_business_context(table_profiles: List[Dict], relationships: List[Dict]) -> str:
    top = sorted(table_profiles, key=lambda x: x["estimated_total_rows"], reverse=True)
    low_quality = sorted(table_profiles, key=lambda x: x["quality_score"])[:3]

    lines = [
        "Nexus detected a relational environment with cross-table dependencies and operational telemetry.",
        f"Largest table by volume: {top[0]['table']} ({top[0]['estimated_total_rows']} rows)." if top else "No tables available.",
        f"Relationships discovered: {len(relationships)} candidate foreign-key links.",
    ]

    if low_quality:
        weak_tables = ", ".join([f"{x['table']} ({x['quality_score']}%)" for x in low_quality])
        lines.append(f"Data quality risks are concentrated in: {weak_tables}.")

    action = [
        "Prioritize key constraints and missingness remediation in low-score tables.",
        "Use relationship confidence above 0.75 for direct ER governance, and manually review the rest.",
        "Operationalize dictionary exports as a living contract for analytics and application teams.",
    ]
    return "\n".join(lines + [""] + action)


def build_dictionary(table_profiles: List[Dict]) -> pd.DataFrame:
    records: List[Dict] = []
    for profile in table_profiles:
        table = profile["table"]
        pks = set(profile["pk_candidates"])
        for cp in profile["column_profiles"]:
            records.append(
                {
                    "table": table,
                    "column": cp["column"],
                    "data_type": cp["sample_dtype"],
                    "role": cp["semantic_role"],
                    "is_primary_candidate": cp["column"] in pks,
                    "null_percent": cp["null_percent"],
                    "unique_percent": cp["unique_percent"],
                    "quality_note": (
                        "High quality"
                        if cp["null_percent"] < 10 and cp["type_consistency"] > 0.9
                        else "Review recommended"
                    ),
                    "example_values": cp["sample_values"],
                    "description": f"{cp['column']} is a {cp['semantic_role']} field in {table}.",
                }
            )
    return pd.DataFrame(records)


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
    engine = create_engine(url, pool_pre_ping=True)
    inspector = inspect(engine)

    tables: Dict[str, pd.DataFrame] = {}
    row_counts: Dict[str, int] = {}
    explicit_relationships: List[Dict] = []

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

    return tables, row_counts, explicit_relationships


def build_er_graph_html(table_profiles: List[Dict], relationships: List[Dict]) -> str:
    net = Network(height="620px", width="100%", directed=True, bgcolor="#0f2233", font_color="#ecf2f9")

    profile_map = {tp["table"]: tp for tp in table_profiles}
    for tp in table_profiles:
        table = tp["table"]
        score = tp["quality_score"]
        size = int(20 + min(30, math.log(max(2, tp["estimated_total_rows"]), 10) * 10))
        color = "#7ee787" if score >= 80 else "#f6d365" if score >= 60 else "#ff7b72"
        title = (
            f"Table: {table} | Rows: {tp['estimated_total_rows']} | "
            f"Columns: {tp['column_count']} | Quality: {score}%"
        )
        net.add_node(table, label=table, color=color, shape="dot", size=size, title=title)

    for rel in relationships:
        label = f"{rel['child_column']} -> {rel['parent_column']} ({rel['confidence']:.2f})"
        edge_color = "#7ee787" if rel["confidence"] >= 0.8 else "#f6d365"
        net.add_edge(rel["child_table"], rel["parent_table"], label=label, color=edge_color)

    net.set_options(
        """
        var options = {
            "nodes": {"font": {"size": 18, "face": "Space Grotesk"}},
            "edges": {
                "arrows": {"to": {"enabled": true, "scaleFactor": 0.7}},
                "font": {"size": 12, "align": "top"},
                "smooth": false
            },
            "physics": {
                "forceAtlas2Based": {"gravitationalConstant": -80, "springLength": 170},
                "minVelocity": 0.75,
                "solver": "forceAtlas2Based"
            }
        }
        """
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            html = f.read()
    os.unlink(tmp.name)
    return html


def format_mermaid(relationships: List[Dict]) -> str:
    lines = ["erDiagram"]
    seen = set()
    for rel in relationships:
        key = (rel["parent_table"], rel["child_table"], rel["child_column"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"  {rel['parent_table']} ||--o{{ {rel['child_table']} : \"{rel['parent_column']}->{rel['child_column']}\""
        )
    return "\n".join(lines)


def audit_load() -> List[Dict]:
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def audit_commit(payload: Dict, actor: str = "Team") -> Dict:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    hash_value = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "artifact": "analysis_snapshot",
        "tables": len(payload.get("table_profiles", [])),
        "relationships": len(payload.get("relationships", [])),
        "hash": hash_value,
        "status": "locked",
    }
    ledger = audit_load()
    ledger.append(entry)
    with open(AUDIT_FILE, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)
    return entry


def ollama_get_models(endpoint: str) -> List[str]:
    try:
        res = requests.get(endpoint.rstrip("/") + "/api/tags", timeout=3)
        if res.status_code != 200:
            return []
        payload = res.json()
        models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        return models
    except requests.RequestException:
        return []


def generate_ai_brief(analysis: Dict, model: str, endpoint: str) -> str:
    top_tables = sorted(analysis["table_profiles"], key=lambda x: x["quality_score"])[:4]
    issues = []
    for t in top_tables:
        issues.extend(t["issues"][:3])

    prompt = f"""
You are an enterprise principal data architect.
Summarize this relational database assessment for engineering leadership.

Context:
- Source type: {analysis['source_type']}
- Tables: {len(analysis['table_profiles'])}
- Relationships discovered: {len(analysis['relationships'])}
- Average quality score: {analysis['avg_quality_score']}

Critical issues:
{chr(10).join('- ' + i for i in issues[:10]) if issues else '- No major issues detected in current sample.'}

Output format:
1) Executive Summary (max 5 bullets)
2) Top Risks (max 5 bullets)
3) 48-Hour Remediation Plan (max 5 bullets)
4) 30-Day Data Governance Plan (max 5 bullets)
"""

    url = endpoint.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    response = requests.post(url, json=payload, timeout=45)
    if response.status_code == 404:
        installed = ollama_get_models(endpoint)
        installed_txt = ", ".join(installed) if installed else "none detected"
        raise RuntimeError(
            f"Model '{model}' not found in Ollama. Installed models: {installed_txt}. "
            "Pull a model with: ollama pull <model_name>."
        )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def run_analysis(
    source_type: str,
    file_map: Dict[str, bytes],
    profile_row_limit: int,
    db_config: Optional[DBConnectionConfig] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict:
    def emit(progress_value: int, message: str) -> None:
        if progress_callback:
            progress_callback(progress_value, message)

    emit(5, "Ingesting source data")
    if source_type == "SQLite":
        only_file = next(iter(file_map.values()))
        tables, row_counts, explicit_relationships = sqlite_ingest(only_file, profile_row_limit)
    elif source_type == "DB Connection":
        if not db_config:
            raise RuntimeError("DB connection mode selected without db_config.")
        tables, row_counts, explicit_relationships = database_ingest(db_config, profile_row_limit)
    else:
        fake_uploads = []
        for file_name, content in file_map.items():
            fake_obj = type("Uploaded", (), {})()
            fake_obj.name = file_name
            fake_obj.getvalue = lambda content=content: content
            fake_uploads.append(fake_obj)
        tables, row_counts = csv_ingest(fake_uploads, profile_row_limit)
        explicit_relationships = []

    if not tables:
        return {}

    emit(20, "Inferring key candidates")
    pk_map = {table: infer_primary_keys(df) for table, df in tables.items()}

    emit(35, "Inferring relationships")
    inferred_relationships = infer_foreign_keys(tables, pk_map)

    rel_keys = set()
    merged_relationships: List[Dict] = []
    for rel in explicit_relationships + inferred_relationships:
        key = (rel["child_table"], rel["child_column"], rel["parent_table"], rel["parent_column"])
        if key in rel_keys:
            continue
        rel_keys.add(key)
        merged_relationships.append(rel)

    emit(55, "Profiling data quality")
    table_profiles = []
    for table_name, df in tables.items():
        total_rows = row_counts.get(table_name, len(df))
        profile = profile_table(table_name, df, total_rows, pk_map.get(table_name, []))
        table_profiles.append(profile)

    emit(75, "Building data dictionary")
    avg_quality = round(float(np.mean([t["quality_score"] for t in table_profiles])) if table_profiles else 0.0, 2)
    dictionary_df = build_dictionary(table_profiles)

    emit(88, "Generating business context and ER view")
    business_context = compute_business_context(table_profiles, merged_relationships)
    er_html = build_er_graph_html(table_profiles, merged_relationships)

    emit(100, "Analysis complete")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_type": source_type,
        "tables": tables,
        "row_counts": row_counts,
        "pk_map": pk_map,
        "relationships": merged_relationships,
        "table_profiles": table_profiles,
        "avg_quality_score": avg_quality,
        "dictionary": dictionary_df,
        "business_context": business_context,
        "er_html": er_html,
        "mermaid": format_mermaid(merged_relationships),
    }


def render_header(analysis: Dict) -> None:
    st.title(APP_TITLE)
    st.caption("Relational Database Intelligence Agent | Schema Reasoning | Data Quality Governance | Explainable Outputs")

    table_count = len(analysis["table_profiles"])
    relationship_count = len(analysis["relationships"])
    avg_quality = analysis["avg_quality_score"]
    issue_count = sum(len(t["issues"]) for t in analysis["table_profiles"])

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, "Tables", table_count, "modeled assets"),
        (c2, "Relationships", relationship_count, "candidate links"),
        (c3, "Avg Quality", f"{avg_quality}%", "portfolio score"),
        (c4, "Open Risks", issue_count, "rule-based alerts"),
    ]
    for col, label, val, sub in cards:
        with col:
            st.markdown(
                f"""
                <div class='card'>
                    <div class='muted'>{label}</div>
                    <div class='metric-big'>{val}</div>
                    <div class='muted'>{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_metric_explanations() -> None:
    with st.expander("How scoring works (read this first)"):
        st.markdown(
            """
**Data Quality Score**
- Weighted formula: `45% completeness + 35% consistency + 20% freshness`.
- Completeness: percentage of non-null values.
- Consistency: dominant type agreement inside each column.
- Freshness: recency of date/time columns (newer values score higher).

**Relationship Confidence**
- For inferred relationships, confidence is overlap ratio between candidate child keys and parent key values.
- `1.0` means explicit foreign key from source DB metadata.

**ER Graph**
- Node color: green (high quality), amber (medium), red (low quality).
- Node size: table volume proxy.
- Edge labels show `child_col -> parent_col (confidence)`.
            """
        )


def main() -> None:
    init_page()

    with st.sidebar:
        st.header("Ingestion")
        source_type = st.radio("Source", ["SQLite", "CSV Bundle", "DB Connection"], horizontal=True)
        profile_row_limit = st.slider("Rows analyzed per table", 500, 100000, 25000, step=500)

        uploaded_sqlite = None
        uploaded_csv = []
        db_config: Optional[DBConnectionConfig] = None
        if source_type == "SQLite":
            uploaded_sqlite = st.file_uploader("Upload SQLite DB", type=["db", "sqlite", "sqlite3"])
        elif source_type == "CSV Bundle":
            uploaded_csv = st.file_uploader("Upload one or more CSV tables", type=["csv"], accept_multiple_files=True)
        else:
            db_engine = st.selectbox("Database engine", ["MySQL", "PostgreSQL", "SQL Server"])
            host = st.text_input("Host", value="localhost")
            port_defaults = {"MySQL": 3306, "PostgreSQL": 5432, "SQL Server": 1433}
            port = st.number_input("Port", min_value=1, max_value=65535, value=port_defaults[db_engine])
            database = st.text_input("Database name")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            sqlserver_driver = st.text_input("SQL Server ODBC driver", value="ODBC Driver 17 for SQL Server")

            engine_map = {"MySQL": "mysql", "PostgreSQL": "postgres", "SQL Server": "sqlserver"}
            db_config = DBConnectionConfig(
                db_type=engine_map[db_engine],
                host=host,
                port=int(port),
                database=database,
                username=username,
                password=password,
                driver=sqlserver_driver,
            )
            st.caption("Requires local DB drivers: pymysql / psycopg2-binary / pyodbc + ODBC driver.")

        st.markdown("---")
        st.header("AI Copilot")
        ollama_endpoint = st.text_input("Ollama endpoint", value="http://localhost:11434")
        available_models = ollama_get_models(ollama_endpoint)
        custom_model = st.text_input("Custom model (optional)", value="")
        if available_models:
            default_idx = 0
            llm_model = st.selectbox("Installed models", available_models, index=default_idx)
            st.success(f"Ollama reachable | {len(available_models)} model(s) detected")
        else:
            llm_model = "llama3:latest"
            st.text_input("Installed models", value="No models detected", disabled=True)
            st.warning("Ollama not detected; deterministic features still run fully.")
        if custom_model.strip():
            llm_model = custom_model.strip()

        st.markdown("---")
        actor = st.text_input("Audit actor", value="HackathonTeam")

    file_map: Dict[str, bytes] = {}
    if source_type == "SQLite" and uploaded_sqlite is not None:
        file_map[uploaded_sqlite.name] = uploaded_sqlite.getvalue()
    elif source_type == "CSV Bundle" and uploaded_csv:
        for f in uploaded_csv:
            file_map[f.name] = f.getvalue()
    elif source_type == "DB Connection":
        file_map = {"db_connection": b"ready"}

    if not file_map:
        st.title(APP_TITLE)
        st.markdown(
            """
            <div class='card'>
                <h3>High-Impact Data Intelligence for Relational Systems</h3>
                <p class='muted'>Upload a SQLite database or a set of CSV tables. Nexus will auto-detect schema structure,
                infer relationships, profile data quality, generate a human-readable data dictionary, and produce
                enterprise exports with an immutable audit hash.</p>
                <span class='pill'>Schema Understanding</span>
                <span class='pill'>ER Intelligence</span>
                <span class='pill'>Quality Scoring</span>
                <span class='pill'>Business Context</span>
                <span class='pill'>Auditability</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    progress = st.progress(0, text="Waiting to start")
    def progress_callback(progress_value: int, message: str) -> None:
        progress.progress(progress_value, text=message)

    with st.spinner("Running schema intelligence pipeline..."):
        analysis = run_analysis(
            source_type,
            file_map,
            profile_row_limit,
            db_config=db_config,
            progress_callback=progress_callback,
        )
    progress.empty()

    if not analysis:
        st.error("Unable to analyze source. Validate file format and try again.")
        return

    render_header(analysis)
    render_metric_explanations()

    overview_tab, schema_tab, relation_tab, quality_tab, dictionary_tab, ai_tab, export_tab = st.tabs(
        ["Overview", "Schema", "ER Graph", "Data Quality", "Data Dictionary", "AI Analyst", "Exports & Audit"]
    )

    with overview_tab:
        left, right = st.columns([1.2, 1])
        with left:
            st.subheader("Business Context Summary")
            st.text(analysis["business_context"])

            profile_df = pd.DataFrame(
                [
                    {
                        "table": p["table"],
                        "rows": p["estimated_total_rows"],
                        "columns": p["column_count"],
                        "quality_score": p["quality_score"],
                        "pk_candidates": ", ".join(p["pk_candidates"]) if p["pk_candidates"] else "None",
                    }
                    for p in analysis["table_profiles"]
                ]
            ).sort_values("quality_score")
            st.dataframe(profile_df, use_container_width=True, hide_index=True)

        with right:
            st.subheader("Quality Score Distribution")
            score_df = pd.DataFrame(
                [{"table": p["table"], "quality_score": p["quality_score"]} for p in analysis["table_profiles"]]
            )
            st.bar_chart(score_df.set_index("table"))

            risks = []
            for p in analysis["table_profiles"]:
                for issue in p["issues"]:
                    risks.append({"table": p["table"], "issue": issue})
            st.subheader("Top Rule Alerts")
            if risks:
                st.dataframe(pd.DataFrame(risks).head(12), use_container_width=True, hide_index=True)
            else:
                st.success("No critical alerts triggered on analyzed sample.")

    with schema_tab:
        tables = [p["table"] for p in analysis["table_profiles"]]
        selected = st.selectbox("Table", tables)
        selected_profile = next(p for p in analysis["table_profiles"] if p["table"] == selected)

        st.markdown(
            f"<div class='pill'>Rows: {selected_profile['estimated_total_rows']}</div>"
            f"<div class='pill'>Columns: {selected_profile['column_count']}</div>"
            f"<div class='pill'>Quality: {selected_profile['quality_score']}%</div>",
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns([1.1, 1])
        with col_a:
            st.subheader("Sample Data")
            st.dataframe(analysis["tables"][selected], use_container_width=True, hide_index=True, height=350)
        with col_b:
            st.subheader("Column Profile")
            col_df = pd.DataFrame(selected_profile["column_profiles"])
            st.dataframe(
                col_df[
                    [
                        "column",
                        "sample_dtype",
                        "semantic_role",
                        "null_percent",
                        "unique_percent",
                        "dominant_value_type",
                        "type_consistency",
                        "freshness_lag_days",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=350,
            )

    with relation_tab:
        st.subheader("Entity Relationship Intelligence")
        st.caption(
            "This graph shows how tables connect. Edge labels are `child -> parent` and confidence. "
            "Higher confidence means stronger evidence of a relationship."
        )
        components.html(analysis["er_html"], height=650, scrolling=True)
        rel_df = pd.DataFrame(analysis["relationships"])
        if not rel_df.empty and "confidence" in rel_df.columns:
            rel_df = rel_df.sort_values("confidence", ascending=False)
        if not rel_df.empty:
            st.dataframe(rel_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No relationships inferred with current data sample.")

    with quality_tab:
        quality_df = pd.DataFrame(
            [
                {
                    "table": p["table"],
                    "quality_score": p["quality_score"],
                    "completeness_score": p["completeness_score"],
                    "consistency_score": p["consistency_score"],
                    "freshness_score": p["freshness_score"],
                    "duplicate_pk_records": p["duplicate_pk_records"],
                }
                for p in analysis["table_profiles"]
            ]
        ).sort_values("quality_score")
        st.dataframe(quality_df, use_container_width=True, hide_index=True)

        chosen_table = st.selectbox("Inspect table quality details", quality_df["table"].tolist())
        detail = next(p for p in analysis["table_profiles"] if p["table"] == chosen_table)
        st.progress(min(1.0, detail["quality_score"] / 100.0), text=f"{detail['quality_score']} / 100 quality score")
        if detail["issues"]:
            st.error("Detected issues:")
            for issue in detail["issues"]:
                st.write(f"- {issue}")
        else:
            st.success("No issue rules triggered for this table in analyzed sample.")

    with dictionary_tab:
        st.subheader("Human-Readable Data Dictionary")
        dict_df = analysis["dictionary"]
        table_filter = st.selectbox("Filter by table", ["All"] + sorted(dict_df["table"].unique().tolist()))
        show_df = dict_df if table_filter == "All" else dict_df[dict_df["table"] == table_filter]
        st.dataframe(show_df, use_container_width=True, hide_index=True, height=420)

        csv_data = show_df.to_csv(index=False).encode("utf-8")
        json_data = show_df.to_json(orient="records", indent=2).encode("utf-8")
        st.download_button("Download dictionary CSV", data=csv_data, file_name="data_dictionary.csv", mime="text/csv")
        st.download_button(
            "Download dictionary JSON",
            data=json_data,
            file_name="data_dictionary.json",
            mime="application/json",
        )

    with ai_tab:
        st.subheader("AI Strategy Analyst")
        st.caption("Uses local Ollama if available; fallback remains deterministic in other tabs.")

        if st.button("Generate executive AI brief"):
            try:
                with st.spinner("Generating AI brief..."):
                    ai_text = generate_ai_brief(analysis, llm_model, ollama_endpoint)
                    st.session_state["ai_brief"] = ai_text
            except Exception as exc:
                st.session_state["ai_brief"] = f"AI generation failed: {exc}"

        existing = st.session_state.get("ai_brief", "Press 'Generate executive AI brief' to produce a strategy summary.")
        edited = st.text_area("Executive brief", value=existing, height=340)
        st.session_state["ai_brief"] = edited

    with export_tab:
        st.subheader("Export Package")
        profile_export = pd.DataFrame(analysis["table_profiles"])
        rel_export = pd.DataFrame(analysis["relationships"])

        full_export = {
            "generated_at": analysis["generated_at"],
            "source_type": analysis["source_type"],
            "avg_quality_score": analysis["avg_quality_score"],
            "table_profiles": analysis["table_profiles"],
            "relationships": analysis["relationships"],
            "business_context": analysis["business_context"],
            "ai_brief": st.session_state.get("ai_brief", ""),
        }
        export_json = json.dumps(full_export, indent=2, default=str).encode("utf-8")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "Download analysis JSON",
                data=export_json,
                file_name="nexus_analysis.json",
                mime="application/json",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download relationships CSV",
                data=rel_export.to_csv(index=False).encode("utf-8"),
                file_name="relationships.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with c3:
            st.download_button(
                "Download ER Mermaid",
                data=analysis["mermaid"].encode("utf-8"),
                file_name="er_diagram.mmd",
                mime="text/plain",
                use_container_width=True,
            )

        st.markdown("---")
        st.subheader("Immutable Audit Ledger")
        if st.button("Commit analysis snapshot", use_container_width=True):
            entry = audit_commit(full_export, actor=actor)
            st.success(f"Snapshot committed. Hash: {entry['hash']}")

        ledger = audit_load()
        if ledger:
            st.dataframe(pd.DataFrame(ledger).iloc[::-1], use_container_width=True, hide_index=True, height=280)
        else:
            st.info("No snapshot committed yet.")


if __name__ == "__main__":
    main()