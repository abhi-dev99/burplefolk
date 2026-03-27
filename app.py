import json
import os
import re
import threading
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from nexus.ai import (
    ollama_get_models,
    test_gemini_connection,
    test_ollama_connection,
)
from nexus.analysis import run_analysis
from nexus.agent_email import (
    AgentLoopConfig,
    firebase_email_password_login,
    get_event_log,
    process_agent_inbox_once,
    run_agent_inbox_loop,
)
from nexus.audit import audit_commit, audit_load
from nexus.ingestion import format_db_connection_error, test_database_connection
from nexus.models import APP_TITLE, DBConnectionConfig
from nexus.orchestration import orchestrate_llm_task
from nexus.provisioning import provision_mysql_from_dictionary, test_mysql_connection


SCHEMA_CHANGE_LOG_FILE = Path("schema_change_history.jsonl")


def _norm_value(value):
    if pd.isna(value):
        return ""
    return str(value)


def _prepare_dictionary_frame(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    if "_row_id" not in prepared.columns:
        prepared["_row_id"] = prepared["table"].astype(str) + "." + prepared["column"].astype(str)
    return prepared.set_index("_row_id", drop=False)


def _compute_dictionary_changes(before_df: pd.DataFrame, after_df: pd.DataFrame, actor: str) -> List[Dict]:
    tracked_columns = ["data_type", "role", "is_primary_candidate", "quality_note", "description"]
    changes: List[Dict] = []

    shared_ids = sorted(set(before_df.index) & set(after_df.index))
    for row_id in shared_ids:
        before_row = before_df.loc[row_id]
        after_row = after_df.loc[row_id]
        for col in tracked_columns:
            before_val = _norm_value(before_row.get(col))
            after_val = _norm_value(after_row.get(col))
            if before_val == after_val:
                continue
            changes.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor": actor,
                    "row_id": row_id,
                    "table": after_row.get("table", ""),
                    "column": after_row.get("column", ""),
                    "field": col,
                    "before": before_val,
                    "after": after_val,
                }
            )

    return changes


def _append_schema_change_log(changes: List[Dict]) -> None:
    if not changes:
        return
    with SCHEMA_CHANGE_LOG_FILE.open("a", encoding="utf-8") as fh:
        for item in changes:
            fh.write(json.dumps(item, default=str) + "\n")


def _extract_svg_from_erd_html(erd_html: str) -> str:
    match = re.search(r"(<svg\b[\s\S]*?</svg>)", erd_html, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _svg_to_png_bytes(svg_markup: str) -> Optional[bytes]:
    if not svg_markup.strip():
        return None
    try:
        import cairosvg  # type: ignore

        return cairosvg.svg2png(bytestring=svg_markup.encode("utf-8"))
    except Exception:
        return None


def _build_enterprise_pdf_report(
    analysis: Dict,
    ai_brief: str,
    dictionary_df: pd.DataFrame,
    relationship_df: pd.DataFrame,
    actor: str,
) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
        from reportlab.lib.units import mm  # type: ignore
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore
    except Exception:
        return None, "PDF export requires reportlab. Install with: pip install reportlab"

    table_profiles = analysis.get("table_profiles", []) if isinstance(analysis.get("table_profiles"), list) else []
    relationships = analysis.get("relationships", []) if isinstance(analysis.get("relationships"), list) else []

    high_conf = [r for r in relationships if float(r.get("confidence", 0) or 0) >= 0.85]
    mid_conf = [r for r in relationships if 0.70 <= float(r.get("confidence", 0) or 0) < 0.85]
    low_conf = [r for r in relationships if float(r.get("confidence", 0) or 0) < 0.70]

    top_risks = sorted(
        table_profiles,
        key=lambda x: float(x.get("quality_score", 0) or 0),
    )[:8]

    role_counts: Dict[str, int] = {}
    if not dictionary_df.empty and "role" in dictionary_df.columns:
        for role, count in dictionary_df["role"].fillna("unknown").value_counts().items():
            role_counts[str(role)] = int(count)

    clean_brief = str(ai_brief or "").strip()
    clean_brief = re.sub(r"\*\*(.*?)\*\*", r"\1", clean_brief)
    clean_brief = re.sub(r"`([^`]+)`", r"\1", clean_brief)
    clean_brief = re.sub(r"^#+\s*", "", clean_brief, flags=re.M)
    if not clean_brief:
        clean_brief = "AI brief is not available for this run."

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Nexus Intelligence Executive Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=8,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#111827"),
        spaceAfter=3,
    )

    story = []
    story.append(Paragraph("Nexus Intelligence | Executive Data Intelligence Report", title_style))
    story.append(Paragraph("Enterprise-grade schema, quality, and governance assessment", body_style))
    story.append(Spacer(1, 4))

    summary_rows = [
        ["Generated at", str(analysis.get("generated_at", "n/a"))],
        ["Actor", actor or "n/a"],
        ["Source type", str(analysis.get("source_type", "n/a"))],
        ["Tables analyzed", str(len(table_profiles))],
        ["Relationships inferred", str(len(relationships))],
        ["Average quality score", str(analysis.get("avg_quality_score", "n/a"))],
        ["Relationship confidence", f"high={len(high_conf)}, mid={len(mid_conf)}, low={len(low_conf)}"],
    ]
    summary_table = Table(summary_rows, colWidths=[42 * mm, 134 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E2E8F0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94A3B8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_table)

    story.append(Paragraph("Top Risk Tables", section_style))
    if top_risks:
        risk_rows = [["Table", "Quality", "Completeness", "Consistency", "Issues", "Duplicate PK"]]
        for item in top_risks:
            risk_rows.append(
                [
                    str(item.get("table", "unknown")),
                    str(item.get("quality_score", "n/a")),
                    str(item.get("completeness_score", "n/a")),
                    str(item.get("consistency_score", "n/a")),
                    str(len(item.get("issues", []))) if isinstance(item.get("issues"), list) else "0",
                    str(item.get("duplicate_pk_records", "0")),
                ]
            )
        risk_table = Table(risk_rows, colWidths=[34 * mm, 20 * mm, 26 * mm, 24 * mm, 20 * mm, 24 * mm])
        risk_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.HexColor("#EEF2FF")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(risk_table)
    else:
        story.append(Paragraph("No table-level risk data was available in this run.", body_style))

    if role_counts:
        story.append(Paragraph("Dictionary Role Distribution", section_style))
        role_rows = [["Semantic role", "Column count"]]
        for role, count in sorted(role_counts.items(), key=lambda kv: kv[1], reverse=True)[:12]:
            role_rows.append([role, str(count)])
        role_table = Table(role_rows, colWidths=[110 * mm, 66 * mm])
        role_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(role_table)

    story.append(Paragraph("AI Executive Brief", section_style))
    for block in [segment.strip() for segment in clean_brief.split("\n\n") if segment.strip()]:
        story.append(Paragraph(block.replace("\n", "<br/>"), body_style))

    if not relationship_df.empty:
        story.append(Paragraph("Key Relationships (Top 20)", section_style))
        rel_rows = [["Child", "Parent", "Type", "Confidence"]]
        rel_sorted = relationship_df.copy()
        if "confidence" in rel_sorted.columns:
            rel_sorted = rel_sorted.sort_values("confidence", ascending=False)
        for _, row in rel_sorted.head(20).iterrows():
            rel_rows.append(
                [
                    f"{row.get('child_table', '?')}.{row.get('child_column', '?')}",
                    f"{row.get('parent_table', '?')}.{row.get('parent_column', '?')}",
                    str(row.get("relation_type", "many-to-one")),
                    str(row.get("confidence", "n/a")),
                ]
            )
        rel_table = Table(rel_rows, colWidths=[62 * mm, 62 * mm, 28 * mm, 24 * mm])
        rel_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.7),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(rel_table)

    doc.build(story)
    return buffer.getvalue(), None


def _read_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    if value is None:
        return default
    return str(value)


def _get_firebase_runtime_config() -> Dict[str, str]:
    return {
        "apiKey": _read_secret("FIREBASE_API_KEY", os.getenv("FIREBASE_API_KEY", "")),
        "authDomain": _read_secret("FIREBASE_AUTH_DOMAIN", os.getenv("FIREBASE_AUTH_DOMAIN", "")),
        "projectId": _read_secret("FIREBASE_PROJECT_ID", os.getenv("FIREBASE_PROJECT_ID", "")),
        "storageBucket": _read_secret("FIREBASE_STORAGE_BUCKET", os.getenv("FIREBASE_STORAGE_BUCKET", "")),
        "defaultAgentEmail": _read_secret("AGENT_DEFAULT_EMAIL", os.getenv("AGENT_DEFAULT_EMAIL", "burplefolk@gmail.com")),
    }


def init_page() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
        :root {
            --bg-gradient-a: #f5f8ff;
            --bg-gradient-b: #eef3ff;
            --surface: rgba(255, 255, 255, 0.86);
            --surface-soft: rgba(241, 245, 255, 0.95);
            --accent: #1d4ed8;
            --accent-2: #0369a1;
            --text: #0f172a;
            --muted: #475569;
            --danger: #b91c1c;
            --ok: #15803d;
            --tab-bg: rgba(237, 242, 255, 0.9);
            --tab-border: rgba(148, 163, 184, 0.45);
            --tab-selected: rgba(59, 130, 246, 0.22);
            --button-bg: linear-gradient(140deg, rgba(59, 130, 246, .14), rgba(14, 165, 233, .16));
            --button-border: rgba(37, 99, 235, .55);
            --button-text: #0f172a;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-gradient-a: #091624;
                --bg-gradient-b: #08131f;
                --surface: rgba(19,40,58,.85);
                --surface-soft: rgba(29,52,73,.9);
                --accent: #f6d365;
                --accent-2: #fda085;
                --text: #eaf1f8;
                --muted: #a4b6c7;
                --danger: #ff7b72;
                --ok: #7ee787;
                --tab-bg: rgba(24, 46, 66, 0.85);
                --tab-border: rgba(164,182,199,0.26);
                --tab-selected: rgba(246,211,101,.24);
                --button-bg: linear-gradient(140deg, rgba(246, 211, 101, .18), rgba(253, 160, 133, .18));
                --button-border: rgba(246, 211, 101, .6);
                --button-text: #fefbf2;
            }
        }
        .stApp {
            background:
                radial-gradient(1200px 500px at 10% 0%, rgba(59, 130, 246, 0.12), transparent),
                radial-gradient(900px 500px at 90% 10%, rgba(14, 165, 233, 0.12), transparent),
                linear-gradient(180deg, var(--bg-gradient-a), var(--bg-gradient-b));
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
        }
        h1, h2, h3, h4 { color: var(--accent); letter-spacing: 0.4px; }
        .card {
            border: 1px solid var(--tab-border);
            border-radius: 12px;
            background: linear-gradient(160deg, var(--surface), var(--surface-soft));
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
            border: 1px solid var(--tab-border);
            background: var(--tab-bg);
            margin-right: 0.4rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            overflow-x: auto;
            scrollbar-width: thin;
        }
        .stTabs [data-baseweb="tab"] {
            min-width: 150px;
            justify-content: center;
            background: var(--tab-bg);
            border-radius: 9px;
            border: 1px solid var(--tab-border);
            padding: 0.55rem 0.9rem;
            color: var(--text);
        }
        .stTabs [aria-selected="true"] {
            border-color: var(--accent);
            background: var(--tab-selected);
            box-shadow: inset 0 0 0 1px var(--accent);
        }
        .stDataFrame { border: 1px solid rgba(164,182,199,0.35); border-radius: 10px; }
        div[data-testid="stFileUploader"] {
            background: var(--surface);
            border: 1px dashed var(--tab-border);
            border-radius: 12px;
            padding: 0.6rem;
        }
        .stButton > button {
            border-radius: 8px;
            border: 1px solid var(--button-border);
            background: var(--button-bg);
            color: var(--button-text);
            font-weight: 600;
        }
        .stDownloadButton > button {
            border-radius: 8px;
            border: 1px solid var(--tab-border);
            background: var(--tab-bg);
            color: var(--text);
            font-weight: 600;
        }
        .agent-icon-btn {
            font-size: 1.5rem;
            cursor: pointer;
            text-align: center;
        }
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 999;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .modal-content {
            background: var(--surface);
            border: 1px solid var(--tab-border);
            border-radius: 12px;
            padding: 2rem;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
- Base formula: `50% completeness + 50% consistency`.
- Temporal regularity adjustment: `bonus/penalty up to +/-10 points`.
- In plain language: if data arrives at its usual rhythm, score gets a bonus; if updates become erratic or slow down sharply, score gets a penalty.
- Expected rhythm is user-defined in the Data Quality tab (for example, `1 day`, `2 weeks`, `3 months`).
- Completeness: percentage of non-null values.
- Consistency: dominant type agreement inside each column.
- Temporal regularity: compares the latest observed interval to your chosen expected cadence.

**Relationship Confidence**
- For inferred relationships, confidence is overlap ratio between candidate child keys and parent key values.
- `1.0` means explicit foreign key from source DB metadata.

**ER Graph**
- Tables are rendered as entity cards with field-level tags (`PK`, `FK`, `PK/FK`).
- Edge labels show `child_col -> parent_col` for inferred key links.
- Colors indicate data quality health (green high, amber medium, red low).
            """
        )


def agent_dashboard() -> None:
    """Dedicated Agent Settings and Control Page."""
    init_page()
    firebase_cfg = _get_firebase_runtime_config()
    
    st.title("Agent Dashboard")
    st.markdown("Configure your Gmail automation agent and monitor activity.")
    st.markdown("---")
    
    agent_auth_state = st.session_state.get("agent_auth_state", {})
    
    # Navigation + logout
    col1, col2, col3 = st.columns([0.2, 0.6, 0.2])
    with col1:
        if st.button("Back to Home", use_container_width=True, key="agent_dashboard_home"):
            st.session_state["agent_page_active"] = False
            st.rerun()
    with col3:
        if st.button("Logout", use_container_width=True, key="agent_dashboard_logout"):
            st.session_state["agent_auth_state"] = {"ok": False, "email": "", "idToken": ""}
            st.session_state["agent_page_active"] = False
            st.rerun()
    
    st.markdown("---")
    
    if agent_auth_state.get("ok"):
        st.success(f"Logged in as: {agent_auth_state.get('email')}")
        
        # Gmail Configuration Section
        st.subheader("Gmail Configuration")
        st.markdown("Configure your Gmail inbox automation:")
        
        default_agent_email = agent_auth_state.get('email') or "burplefolk@gmail.com"
        agent_email = st.text_input("Agent Gmail", value=default_agent_email, key="agent_email_address_dashboard")
        gmail_app_password = st.text_input("Gmail App Password", type="password", key="agent_gmail_app_password_dashboard")
        imap_host = st.text_input("IMAP Host", value="imap.gmail.com", key="agent_imap_host_dashboard")
        smtp_host = st.text_input("SMTP Host", value="smtp.gmail.com", key="agent_smtp_host_dashboard")
        smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=587, key="agent_smtp_port_dashboard")
        poll_seconds = st.slider("Inbox poll interval (seconds)", min_value=15, max_value=600, value=60, step=15, key="agent_poll_seconds_dashboard")
        max_messages = st.slider("Max emails per cycle", min_value=1, max_value=20, value=5, step=1, key="agent_max_messages_dashboard")

        enable_auto_reply = st.checkbox(
            "Enable automatic reply-all",
            value=bool(st.session_state.get("agent_auto_reply_enabled", False)),
            key="agent_auto_reply_enabled_dashboard",
        )

        # Sync values back to main session state
        st.session_state["agent_email_address"] = agent_email
        st.session_state["agent_gmail_app_password"] = gmail_app_password
        st.session_state["agent_imap_host"] = imap_host
        st.session_state["agent_smtp_host"] = smtp_host
        st.session_state["agent_smtp_port"] = smtp_port
        st.session_state["agent_poll_seconds"] = poll_seconds
        st.session_state["agent_max_messages"] = max_messages
        st.session_state["agent_auto_reply_enabled"] = enable_auto_reply

        st.markdown("---")
        
        # AI Configuration Section
        st.subheader("AI Query Engine")
        st.markdown("Configure AI provider for automatic query generation from emails:")
        
        ai_provider_label = st.selectbox(
            "AI Provider",
            ["Ollama (local)", "Gemini (API key)"],
            index=0 if st.session_state.get("agent_ai_provider") != "gemini" else 1,
            key="agent_ai_provider_select"
        )
        ai_provider = "gemini" if "Gemini" in ai_provider_label else "ollama"
        
        if ai_provider == "ollama":
            ollama_endpoint = st.text_input(
                "Ollama Endpoint",
                value=st.session_state.get("agent_ollama_endpoint", "http://localhost:11434"),
                key="agent_ollama_endpoint_input"
            )
            available_models = []
            try:
                from nexus.ai import ollama_get_models
                available_models = ollama_get_models(ollama_endpoint)
            except Exception:
                available_models = []
            
            if available_models:
                ollama_model = st.selectbox(
                    "Model",
                    available_models,
                    index=0,
                    key="agent_ollama_model_select"
                )
                st.success(f"Ollama detected: {len(available_models)} model(s) available")
            else:
                ollama_model = st.text_input("Model (custom)", value="llama2", key="agent_ollama_model_custom")
                st.warning("No Ollama models auto-detected. Enter model name manually.")
            
            st.session_state["agent_ai_provider"] = "ollama"
            st.session_state["agent_ollama_endpoint"] = ollama_endpoint
            st.session_state["agent_ollama_model"] = ollama_model
            st.session_state["agent_gemini_api_key"] = ""
            st.session_state["agent_gemini_model"] = ""
        else:
            gemini_api_key = st.text_input(
                "Gemini API Key",
                type="password",
                value=st.session_state.get("agent_gemini_api_key", ""),
                key="agent_gemini_api_key_input"
            )
            gemini_model = st.text_input(
                "Model",
                value=st.session_state.get("agent_gemini_model", "gemini-2.0-flash"),
                key="agent_gemini_model_input"
            )
            
            st.session_state["agent_ai_provider"] = "gemini"
            st.session_state["agent_gemini_api_key"] = gemini_api_key
            st.session_state["agent_gemini_model"] = gemini_model
            st.session_state["agent_ollama_endpoint"] = ""
            st.session_state["agent_ollama_model"] = ""
        
        st.markdown("---")
        
        # Manual Inbox Processing
        st.subheader("Manual Inbox Processing")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Process inbox once now", use_container_width=True, key="agent_process_once_dashboard"):
                tables_snapshot = st.session_state.get("agent_tables_snapshot")
                if not isinstance(tables_snapshot, dict) or not tables_snapshot:
                    st.error("No analyzed tables available yet. Upload and analyze a dataset on the main page first.")
                elif not agent_email or not gmail_app_password:
                    st.error("Enter Agent Gmail and Gmail App Password before processing inbox.")
                else:
                    with st.spinner("Checking agent inbox and preparing reply-all messages..."):
                        summary = process_agent_inbox_once(
                            agent_email=agent_email,
                            gmail_app_password=gmail_app_password,
                            imap_host=imap_host,
                            smtp_host=smtp_host,
                            smtp_port=int(smtp_port),
                            tables=tables_snapshot,
                            max_messages_per_cycle=int(max_messages),
                            ai_provider=st.session_state.get("agent_ai_provider", "ollama"),
                            ollama_endpoint=st.session_state.get("agent_ollama_endpoint", "http://localhost:11434"),
                            ollama_model=st.session_state.get("agent_ollama_model", "llama2"),
                            gemini_api_key=st.session_state.get("agent_gemini_api_key", ""),
                            gemini_model=st.session_state.get("agent_gemini_model", "gemini-2.0-flash"),
                        )

                    if summary.get("replied", 0) > 0:
                        st.success(f"Agent sent {summary.get('replied', 0)} reply-all email(s).")
                    else:
                        st.info(
                            f"No replies sent. Unseen: {summary.get('unseen_count', 0)}, "
                            f"Processed: {summary.get('processed', 0)}, Skipped: {summary.get('skipped', 0)}"
                        )
                        if summary.get("unseen_count", 0) == 0:
                            st.caption("Tip: only unread emails are processed. Mark the email unread and try again.")

                    if summary.get("failures"):
                        st.error("Inbox processing errors: " + " | ".join(summary.get("failures", [])))
        
        with col2:
            current_loop_thread = st.session_state.get("agent_loop_thread")
            if current_loop_thread is not None and current_loop_thread.is_alive():
                st.info("Background agent is running")
            else:
                st.info("Background agent is idle")

        st.caption("Every reply includes: Disclaimer: This content is AI-generated.")
        
        st.markdown("---")
        
        # Activity Log
        st.subheader("Activity Log")
        recent_events = get_event_log(limit=50)
        if recent_events:
            events_df = pd.DataFrame(recent_events)
            st.dataframe(events_df, use_container_width=True, hide_index=True, height=400)
        else:
            st.info("No activity logged yet.")
    else:
        st.error("Not authenticated. Please log in from the main sidebar.")


def _sync_agent_loop_from_snapshot() -> None:
    authed = bool(st.session_state.get("agent_auth_state", {}).get("ok"))
    enable_auto_reply = bool(st.session_state.get("agent_auto_reply_enabled", False))
    agent_email = str(st.session_state.get("agent_email_address", "")).strip()
    gmail_app_password = str(st.session_state.get("agent_gmail_app_password", "")).strip()
    imap_host = str(st.session_state.get("agent_imap_host", "imap.gmail.com")).strip()
    smtp_host = str(st.session_state.get("agent_smtp_host", "smtp.gmail.com")).strip()
    smtp_port = int(st.session_state.get("agent_smtp_port", 587))
    poll_seconds = int(st.session_state.get("agent_poll_seconds", 60))
    max_messages = int(st.session_state.get("agent_max_messages", 5))
    tables_snapshot = st.session_state.get("agent_tables_snapshot", {})

    has_tables = isinstance(tables_snapshot, dict) and bool(tables_snapshot)
    run_agent_loop = bool(authed and enable_auto_reply and agent_email and gmail_app_password and has_tables)

    snapshot_signature = ",".join(sorted(tables_snapshot.keys())) if has_tables else ""
    new_fingerprint = "|".join(
        [
            snapshot_signature,
            agent_email,
            imap_host,
            smtp_host,
            str(smtp_port),
            str(poll_seconds),
            str(max_messages),
            st.session_state.get("agent_ai_provider", "ollama"),
            st.session_state.get("agent_ollama_model", "llama2"),
            st.session_state.get("agent_gemini_model", "gemini-2.0-flash"),
            "enabled" if run_agent_loop else "disabled",
        ]
    )

    existing_thread = st.session_state.get("agent_loop_thread")
    existing_stop_event = st.session_state.get("agent_loop_stop_event")
    existing_fingerprint = st.session_state.get("agent_loop_fingerprint", "")

    if run_agent_loop:
        if existing_thread is None or not existing_thread.is_alive() or existing_fingerprint != new_fingerprint:
            if existing_stop_event is not None:
                existing_stop_event.set()

            stop_event = threading.Event()
            loop_config = AgentLoopConfig(
                agent_email=agent_email,
                gmail_app_password=gmail_app_password,
                imap_host=imap_host,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                interval_seconds=poll_seconds,
                max_messages_per_cycle=max_messages,
                ai_provider=st.session_state.get("agent_ai_provider", "ollama"),
                ollama_endpoint=st.session_state.get("agent_ollama_endpoint", "http://localhost:11434"),
                ollama_model=st.session_state.get("agent_ollama_model", "llama2"),
                gemini_api_key=st.session_state.get("agent_gemini_api_key", ""),
                gemini_model=st.session_state.get("agent_gemini_model", "gemini-2.0-flash"),
            )
            loop_thread = threading.Thread(
                target=run_agent_inbox_loop,
                args=(stop_event, loop_config, tables_snapshot),
                daemon=True,
                name="agent-inbox-loop",
            )
            loop_thread.start()
            st.session_state["agent_loop_thread"] = loop_thread
            st.session_state["agent_loop_stop_event"] = stop_event
            st.session_state["agent_loop_fingerprint"] = new_fingerprint
    else:
        if existing_stop_event is not None:
            existing_stop_event.set()
        st.session_state["agent_loop_thread"] = None
        st.session_state["agent_loop_stop_event"] = None
        st.session_state["agent_loop_fingerprint"] = ""


def main() -> None:
    init_page()
    firebase_cfg = _get_firebase_runtime_config()

    if "agent_auth_state" not in st.session_state:
        st.session_state["agent_auth_state"] = {"ok": False, "email": "", "idToken": ""}
    if "agent_loop_thread" not in st.session_state:
        st.session_state["agent_loop_thread"] = None
    if "agent_loop_stop_event" not in st.session_state:
        st.session_state["agent_loop_stop_event"] = None
    if "agent_loop_fingerprint" not in st.session_state:
        st.session_state["agent_loop_fingerprint"] = ""
    if "agent_manual_run_requested" not in st.session_state:
        st.session_state["agent_manual_run_requested"] = False
    if "agent_page_active" not in st.session_state:
        st.session_state["agent_page_active"] = False
    if "show_agent_login_modal" not in st.session_state:
        st.session_state["show_agent_login_modal"] = False
    if "agent_tables_snapshot" not in st.session_state:
        st.session_state["agent_tables_snapshot"] = {}
    if "analysis_result" not in st.session_state:
        st.session_state["analysis_result"] = None

    _sync_agent_loop_from_snapshot()

    # Check if agent dashboard should be shown
    if st.session_state.get("agent_page_active", False):
        agent_dashboard()
        return

    cadence_days_map = {
        "second": 1.0 / 86400.0,
        "minute": 1.0 / 1440.0,
        "hour": 1.0 / 24.0,
        "half-day": 0.5,
        "day": 1.0,
        "week": 7.0,
        "month": 30.4375,
        "quarter": 91.3125,
        "year": 365.25,
    }
    if "temporal_cadence_value" not in st.session_state:
        st.session_state["temporal_cadence_value"] = 1
    if "temporal_cadence_unit" not in st.session_state:
        st.session_state["temporal_cadence_unit"] = "day"

    temporal_cadence_days = float(st.session_state["temporal_cadence_value"]) * cadence_days_map[
        st.session_state["temporal_cadence_unit"]
    ]
    cadence_label = (
        f"{int(st.session_state['temporal_cadence_value'])} {st.session_state['temporal_cadence_unit']}"
        f"{'' if int(st.session_state['temporal_cadence_value']) == 1 else 's'}"
    )

    with st.sidebar:
        st.header("Ingestion")
        source_type = st.radio("Source", ["SQLite", "CSV Bundle", "DB Connection"], horizontal=True)
        profile_row_limit = st.slider("Rows analyzed per table", 500, 100000, 25000, step=500)

        uploaded_sqlite = None
        uploaded_csv = []
        db_config: Optional[DBConnectionConfig] = None
        db_ready_for_analysis = True
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
            username = st.text_input("Username", value="root")
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
            required_ready = bool(database.strip() and username.strip())

            ingest_fp = "|".join(
                [
                    db_config.db_type,
                    db_config.host.strip(),
                    str(db_config.port),
                    db_config.database.strip(),
                    db_config.username.strip(),
                    db_config.password,
                    db_config.driver,
                ]
            )

            prev_ingest_fp = st.session_state.get("ingest_db_connection_fingerprint")
            if prev_ingest_fp != ingest_fp:
                st.session_state["ingest_db_connection_fingerprint"] = ingest_fp
                st.session_state["ingest_db_connection_state"] = None

            if st.button("Connect database", use_container_width=True, key="test_db_connection"):
                if not required_ready:
                    st.session_state["ingest_db_connection_state"] = {
                        "ok": False,
                        "message": "Enter database name and username before connecting.",
                    }
                else:
                    ok, message = test_database_connection(db_config)
                    st.session_state["ingest_db_connection_state"] = {"ok": ok, "message": message}

            ingest_state = st.session_state.get("ingest_db_connection_state")
            if ingest_state is None:
                st.info("Enter DB credentials and click Connect database before running DB ingestion.")
            elif ingest_state.get("ok"):
                st.success("Connection established. You can run DB ingestion now.")
                st.caption(str(ingest_state.get("message", "")))
            else:
                st.error(str(ingest_state.get("message", "Connection failed.")))

            db_ready_for_analysis = bool(ingest_state and ingest_state.get("ok"))

        st.markdown("---")
        st.header("ERD View")
        erd_detail_label = st.selectbox("Detail level", ["Full schema", "Keys-focused"], index=0)
        erd_layout_label = st.selectbox("Layout", ["Left to right", "Top to bottom"], index=0)
        erd_view_mode = "keys" if erd_detail_label == "Keys-focused" else "full"
        erd_layout_direction = "TB" if erd_layout_label == "Top to bottom" else "LR"

        st.markdown("---")
        st.header("AI Copilot")
        ai_provider_label = st.selectbox("AI provider", ["Ollama (local)", "Gemini (API key)"], index=0)
        ai_provider = "ollama" if ai_provider_label.startswith("Ollama") else "gemini"
        ai_timeout_seconds = st.slider("AI timeout (seconds)", min_value=30, max_value=180, value=60, step=10)

        default_ollama_endpoint = st.secrets.get("OLLAMA_ENDPOINT", os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434"))
        default_ollama_api_key = st.secrets.get("OLLAMA_API_KEY", os.getenv("OLLAMA_API_KEY", ""))

        ollama_endpoint = str(default_ollama_endpoint)
        ollama_api_key = str(default_ollama_api_key)
        gemini_api_key = ""
        available_models: List[str] = []

        if ai_provider == "ollama":
            ollama_endpoint = st.text_input("Ollama endpoint", value=ollama_endpoint)
            ollama_api_key = st.text_input("Ollama API key (optional)", value=ollama_api_key, type="password")

            if "localhost" in ollama_endpoint or "127.0.0.1" in ollama_endpoint:
                st.warning(
                    "localhost only works when running this app on your own machine. "
                    "For Streamlit Cloud, set a public Ollama endpoint in secrets: OLLAMA_ENDPOINT (and OLLAMA_API_KEY if needed)."
                )

            if ":1143" in ollama_endpoint and ":11434" not in ollama_endpoint:
                st.error("Ollama endpoint port looks incorrect. Use port 11434 (for example: http://<ip>:11434).")

            model_list_timeout = max(8, min(ai_timeout_seconds, 30))
            available_models = ollama_get_models(
                ollama_endpoint,
                api_key=ollama_api_key,
                timeout_seconds=model_list_timeout,
            )
            custom_model = st.text_input("Custom model (optional)", value="")
            if available_models:
                llm_model = st.selectbox("Installed models", available_models, index=0)
                st.success(f"Ollama detected | {len(available_models)} model(s) available")
            else:
                llm_model = "llama3:latest"
                st.warning("No Ollama models detected yet.")

            if custom_model.strip():
                llm_model = custom_model.strip()

            if st.button("Test Ollama connection", use_container_width=True, key="test_ai_connection_ollama"):
                test_timeout = max(15, min(ai_timeout_seconds, 45))
                ok, msg, _ = test_ollama_connection(
                    ollama_endpoint,
                    timeout_seconds=test_timeout,
                    api_key=ollama_api_key,
                )
                st.session_state["ai_connection_state"] = {"ok": ok, "message": msg, "provider": "ollama"}

            ai_state = st.session_state.get("ai_connection_state")
            if ai_state and ai_state.get("provider") == "ollama":
                if ai_state.get("ok"):
                    st.success(str(ai_state.get("message", "Connected.")))
                else:
                    st.error(str(ai_state.get("message", "Connection failed.")))

            enable_ai_erd_fallback = st.checkbox(
                "Enable Ollama ERD fallback",
                value=bool(available_models),
                help="If deterministic ER rendering fails, use Ollama to generate layout hints instead of blocking the UI.",
            )
            if not available_models:
                enable_ai_erd_fallback = False
        else:
            gemini_api_key = st.text_input("Gemini API key", type="password", value="")
            llm_model = st.text_input("Gemini model", value="gemini-2.0-flash")

            if st.button("Test Gemini connection", use_container_width=True, key="test_ai_connection_gemini"):
                ok, msg = test_gemini_connection(gemini_api_key, model=llm_model, timeout_seconds=12)
                st.session_state["ai_connection_state"] = {"ok": ok, "message": msg, "provider": "gemini"}

            ai_state = st.session_state.get("ai_connection_state")
            if ai_state and ai_state.get("provider") == "gemini":
                if ai_state.get("ok"):
                    st.success(str(ai_state.get("message", "Connected.")))
                else:
                    st.error(str(ai_state.get("message", "Connection failed.")))

            enable_ai_erd_fallback = False

        st.markdown("---")
        actor = st.text_input("Audit actor", value="HackathonTeam")

        st.markdown("---")
        st.header("Agent")
        agent_auth_state = st.session_state.get("agent_auth_state", {})
        
        if agent_auth_state.get("ok"):
            st.success(f"Logged in as: {agent_auth_state.get('email')}")
            if st.button("Agent Settings", use_container_width=True, key="agent_settings_btn"):
                st.session_state["agent_page_active"] = True
                st.rerun()
        else:
            if st.button("Agent Login", use_container_width=True, key="agent_login_btn_sidebar"):
                st.session_state["show_agent_login_modal"] = True
            
            if st.session_state.get("show_agent_login_modal", False):
                st.markdown("---")
                st.markdown("#### Firebase Login")
                firebase_login_email = st.text_input(
                    "Email",
                    value=agent_auth_state.get("email") or firebase_cfg.get("defaultAgentEmail", "burplefolk@gmail.com"),
                    key="firebase_login_email_sidebar",
                )
                firebase_login_password = st.text_input("Password", type="password", key="firebase_login_password_sidebar")

                login_col1, login_col2 = st.columns(2)
                with login_col1:
                    if st.button("Sign In", use_container_width=True, key="firebase_signin_submit_sidebar"):
                        if not firebase_cfg.get("apiKey"):
                            st.error(
                                "Firebase runtime config is missing: FIREBASE_API_KEY. "
                                "Set it in Streamlit Secrets and reboot the app."
                            )
                        else:
                            ok, msg, user = firebase_email_password_login(
                                firebase_api_key=firebase_cfg["apiKey"],
                                firebase_auth_domain=firebase_cfg["authDomain"],
                                firebase_project_id=firebase_cfg["projectId"],
                                firebase_storage_bucket=firebase_cfg["storageBucket"],
                                email=firebase_login_email,
                                password=firebase_login_password,
                            )
                            if ok:
                                st.session_state["agent_auth_state"] = {
                                    "ok": True,
                                    "email": firebase_login_email,
                                    "idToken": str((user or {}).get("idToken", "")),
                                }
                                st.session_state["show_agent_login_modal"] = False
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                with login_col2:
                    if st.button("Cancel", use_container_width=True, key="firebase_signin_cancel_sidebar"):
                        st.session_state["show_agent_login_modal"] = False
                        st.rerun()
                st.markdown("---")

    current_loop_thread = st.session_state.get("agent_loop_thread")
    if current_loop_thread is not None and current_loop_thread.is_alive():
        st.caption("Agent inbox loop is active in the background.")

    file_map: Dict[str, bytes] = {}
    if source_type == "SQLite" and uploaded_sqlite is not None:
        file_map[uploaded_sqlite.name] = uploaded_sqlite.getvalue()
    elif source_type == "CSV Bundle" and uploaded_csv:
        for f in uploaded_csv:
            file_map[f.name] = f.getvalue()
    elif source_type == "DB Connection":
        file_map = {"db_connection": b"ready"}

    if source_type == "DB Connection" and not db_ready_for_analysis:
        st.title(APP_TITLE)
        st.info("Connect to the database from the sidebar first. Analysis starts only after a successful connection test.")
        return

    cached_analysis = st.session_state.get("analysis_result")
    if not file_map and not cached_analysis:
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

    analysis = cached_analysis
    if file_map:
        progress = st.progress(0, text="Waiting to start")

        def progress_callback(progress_value: int, message: str) -> None:
            progress.progress(progress_value, text=message)

        try:
            with st.spinner("Running schema intelligence pipeline..."):
                analysis = run_analysis(
                    source_type,
                    file_map,
                    profile_row_limit,
                    db_config=db_config,
                    progress_callback=progress_callback,
                    erd_view_mode=erd_view_mode,
                    erd_layout_direction=erd_layout_direction,
                    ollama_model=llm_model if ai_provider == "ollama" else "",
                    ollama_endpoint=ollama_endpoint,
                    enable_ai_erd_fallback=enable_ai_erd_fallback,
                    temporal_cadence_days=temporal_cadence_days,
                )
        except Exception as exc:
            progress.empty()
            if source_type == "DB Connection":
                st.error(format_db_connection_error(exc, db_config))
            else:
                st.error(f"Analysis failed: {exc}")
            return
        progress.empty()

    if not analysis:
        st.error("Unable to analyze source. Validate file format and try again.")
        return

    st.session_state["analysis_result"] = analysis

    st.session_state["agent_tables_snapshot"] = analysis.get("tables", {})

    authed = bool(st.session_state.get("agent_auth_state", {}).get("ok"))
    agent_email = str(st.session_state.get("agent_email_address", "")).strip()
    gmail_app_password = str(st.session_state.get("agent_gmail_app_password", "")).strip()
    imap_host = str(st.session_state.get("agent_imap_host", "imap.gmail.com")).strip()
    smtp_host = str(st.session_state.get("agent_smtp_host", "smtp.gmail.com")).strip()
    smtp_port = int(st.session_state.get("agent_smtp_port", 587))
    max_messages = int(st.session_state.get("agent_max_messages", 5))

    _sync_agent_loop_from_snapshot()

    if st.session_state.get("agent_manual_run_requested") and authed and agent_email and gmail_app_password:
        with st.spinner("Checking agent inbox and preparing reply-all messages..."):
            summary = process_agent_inbox_once(
                agent_email=agent_email,
                gmail_app_password=gmail_app_password,
                imap_host=imap_host,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                tables=analysis["tables"],
                max_messages_per_cycle=max_messages,
                ai_provider=st.session_state.get("agent_ai_provider", "ollama"),
                ollama_endpoint=st.session_state.get("agent_ollama_endpoint", "http://localhost:11434"),
                ollama_model=st.session_state.get("agent_ollama_model", "llama2"),
                gemini_api_key=st.session_state.get("agent_gemini_api_key", ""),
                gemini_model=st.session_state.get("agent_gemini_model", "gemini-2.0-flash"),
            )
        if summary.get("replied", 0) > 0:
            st.success(f"Agent sent {summary.get('replied', 0)} reply-all email(s).")
        else:
            st.info("Inbox processed. No outgoing replies were sent.")
        if summary.get("failures"):
            st.error("Inbox processing errors: " + " | ".join(summary.get("failures", [])))
        st.session_state["agent_manual_run_requested"] = False

    dict_state_key = f"dict::{analysis['generated_at']}"
    if st.session_state.get("dictionary_state_key") != dict_state_key:
        base_dictionary = _prepare_dictionary_frame(analysis["dictionary"])
        st.session_state["dictionary_state_key"] = dict_state_key
        st.session_state["dictionary_baseline"] = base_dictionary.copy()
        st.session_state["dictionary_working"] = base_dictionary.copy()
        st.session_state["dictionary_change_log"] = []

    render_header(analysis)
    render_metric_explanations()

    overview_tab, schema_tab, relation_tab, quality_tab, dictionary_tab, ai_tab, export_tab = st.tabs(
        ["Overview", "Schema", "ER Graph", "Data Quality", "Data Dictionary", "AI Analyst", "Exports & Audit"]
    )

    with overview_tab:
        profile_df = pd.DataFrame(
            [
                {
                    "table": p["table"],
                    "rows": p["estimated_total_rows"],
                    "columns": p["column_count"],
                    "quality_score": p["quality_score"],
                    "issues": len(p["issues"]),
                }
                for p in analysis["table_profiles"]
            ]
        )

        rel_df_overview = pd.DataFrame(analysis["relationships"])
        high_conf_links = int((rel_df_overview.get("confidence", pd.Series(dtype=float)) >= 0.8).sum()) if not rel_df_overview.empty else 0
        total_rows_est = int(profile_df["rows"].sum()) if not profile_df.empty else 0
        total_columns = int(profile_df["columns"].sum()) if not profile_df.empty else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Estimated Rows", f"{total_rows_est:,}")
        with k2:
            st.metric("Total Columns", f"{total_columns}")
        with k3:
            st.metric("High-Confidence Links", f"{high_conf_links}")
        with k4:
            st.metric("Tables Below 85% Quality", f"{int((profile_df['quality_score'] < 85).sum())}")

        worst = profile_df.sort_values("quality_score").head(1)
        largest = profile_df.sort_values("rows", ascending=False).head(1)
        if not worst.empty:
            st.info(f"ℹ Primary risk table: {worst.iloc[0]['table']} ({worst.iloc[0]['quality_score']}%).")
        if not largest.empty:
            st.info(f"ℹ Largest table by volume: {largest.iloc[0]['table']} ({int(largest.iloc[0]['rows']):,} rows).")

        lcol, rcol = st.columns([1.1, 1])
        with lcol:
            st.subheader("Risk Snapshot")
            risk_view = profile_df.sort_values(["quality_score", "issues"]).head(6)
            st.dataframe(
                risk_view[["table", "quality_score", "issues", "rows", "columns"]],
                use_container_width=True,
                hide_index=True,
            )

        with rcol:
            st.subheader("Quality Spread")
            score_df = profile_df[["table", "quality_score"]].sort_values("quality_score")
            st.dataframe(
                score_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "quality_score": st.column_config.ProgressColumn(
                        "quality_score",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    )
                },
            )

        with st.expander("Detailed Context (i)"):
            st.caption("Business context and rationale behind the metrics above.")
            st.text(analysis["business_context"])

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
                        "temporal_expected_gap_days",
                        "temporal_lag_ratio",
                        "temporal_regularity_score",
                        "temporal_adjustment_points",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=350,
            )

    with relation_tab:
        st.subheader("Entity Relationship Intelligence")
        st.caption(
            "This ERD uses table cards and key-level markers (`PK`, `FK`, `PK/FK`) to mirror relational design. "
            "Edge labels are `child_col -> parent_col` links. Use the toolbar to zoom, fit, and reset the layout."
        )
        if analysis.get("erd_renderer") == "ollama-fallback":
            st.info(analysis.get("erd_fallback_note") or "Ollama ERD fallback was used.")
        elif analysis.get("erd_renderer") == "native-safe-fallback":
            st.warning(analysis.get("erd_fallback_note") or "Primary renderer failed; deterministic fallback was used.")
        elif analysis.get("erd_renderer") == "error-safe":
            st.error(analysis.get("erd_fallback_note") or "ERD rendering failed.")

        components.html(analysis["er_html"], height=690, scrolling=False)
        rel_df = pd.DataFrame(analysis["relationships"])
        if not rel_df.empty and "confidence" in rel_df.columns:
            rel_df = rel_df.sort_values("confidence", ascending=False)
        if not rel_df.empty:
            st.dataframe(rel_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No relationships inferred with current data sample.")

    with quality_tab:
        st.subheader("Temporal Cadence Settings")
        q1, q2 = st.columns(2)
        with q1:
            st.number_input(
                "Cadence value",
                min_value=1,
                max_value=1000,
                step=1,
                key="temporal_cadence_value",
            )
        with q2:
            st.selectbox(
                "Cadence unit",
                ["second", "minute", "hour", "half-day", "day", "week", "month", "quarter", "year"],
                key="temporal_cadence_unit",
            )
        st.caption(f"Current expected cadence: {cadence_label}. Changes apply immediately on rerun.")

        quality_df = pd.DataFrame(
            [
                {
                    "table": p["table"],
                    "quality_score": p["quality_score"],
                    "base_quality_score": p.get("base_quality_score", p["quality_score"]),
                    "completeness_score": p["completeness_score"],
                    "consistency_score": p["consistency_score"],
                    "temporal_bonus_points": p.get("temporal_bonus_points", 0.0),
                    "expected_cadence_days": p.get("temporal_expected_cadence_days"),
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
        st.caption("Edit schema fields below, then click Save schema changes to persist and log the modifications.")

        working_dictionary = st.session_state["dictionary_working"].copy()
        baseline_dictionary = st.session_state["dictionary_baseline"].copy()

        table_filter = st.selectbox("Filter by table", ["All"] + sorted(working_dictionary["table"].unique().tolist()))
        display_df = (
            working_dictionary
            if table_filter == "All"
            else working_dictionary[working_dictionary["table"] == table_filter]
        )

        editor_columns = [
            "table",
            "column",
            "data_type",
            "role",
            "is_primary_candidate",
            "null_percent",
            "unique_percent",
            "quality_note",
            "description",
            "example_values",
        ]

        edited_display = st.data_editor(
            display_df[editor_columns],
            use_container_width=True,
            height=460,
            hide_index=True,
            disabled=["table", "column", "null_percent", "unique_percent", "example_values"],
            key=f"dict_editor::{analysis['generated_at']}::{table_filter}",
        )

        merged_dictionary = working_dictionary.copy()
        merged_dictionary.loc[edited_display.index, edited_display.columns] = edited_display
        st.session_state["dictionary_working"] = merged_dictionary

        pending_changes = _compute_dictionary_changes(
            st.session_state["dictionary_baseline"],
            st.session_state["dictionary_working"],
            actor,
        )
        if pending_changes:
            st.warning(f"You have {len(pending_changes)} unsaved schema change(s). Click Save schema changes.")
        else:
            st.success("No unsaved schema edits.")

        if st.button("Save schema changes", use_container_width=True):
            captured = _compute_dictionary_changes(
                st.session_state["dictionary_baseline"],
                st.session_state["dictionary_working"],
                actor,
            )
            if not captured:
                st.info("No changes to save.")
            else:
                _append_schema_change_log(captured)
                st.session_state["dictionary_change_log"].extend(captured)
                st.session_state["dictionary_baseline"] = st.session_state["dictionary_working"].copy()
                st.success(f"Saved {len(captured)} schema change(s).")

        if st.session_state.get("dictionary_change_log"):
            st.markdown("**Saved change notes (current run)**")
            st.dataframe(pd.DataFrame(st.session_state["dictionary_change_log"]), use_container_width=True, hide_index=True, height=180)

        export_view = st.session_state["dictionary_working"].copy()
        if "_row_id" in export_view.columns:
            export_view = export_view.drop(columns=["_row_id"])

        csv_data = export_view.to_csv(index=False).encode("utf-8")
        json_data = export_view.to_json(orient="records", indent=2).encode("utf-8")
        st.download_button("Download dictionary CSV", data=csv_data, file_name="data_dictionary.csv", mime="text/csv")
        st.download_button(
            "Download dictionary JSON",
            data=json_data,
            file_name="data_dictionary.json",
            mime="application/json",
        )

    with ai_tab:
        st.subheader("AI Strategy Analyst")
        if ai_provider == "gemini":
            st.caption("Using Gemini API for AI brief generation.")
        else:
            st.caption("Using local Ollama for AI brief generation.")

        if st.button("Generate executive AI brief"):
            try:
                with st.spinner("Generating AI brief..."):
                    if ai_provider == "gemini":
                        fallback_provider = "gemini"
                    elif gemini_api_key.strip():
                        fallback_provider = "gemini"
                    else:
                        fallback_provider = "ollama"

                    orchestration_result = orchestrate_llm_task(
                        analysis=analysis,
                        task="executive_brief",
                        provider_preference=ai_provider,
                        fallback_provider=fallback_provider,
                        ollama_model=llm_model if ai_provider == "ollama" else "llama3:latest",
                        ollama_endpoint=ollama_endpoint,
                        ollama_api_key=ollama_api_key,
                        gemini_model=llm_model if ai_provider == "gemini" else "gemini-2.0-flash",
                        gemini_api_key=gemini_api_key,
                        timeout_seconds=ai_timeout_seconds,
                    )
                    st.session_state["ai_orchestration"] = orchestration_result
                    st.session_state["ai_brief"] = str(orchestration_result.get("output", "")).strip()
            except Exception as exc:
                st.session_state["ai_brief"] = f"AI generation failed: {exc}"
                st.session_state["ai_orchestration"] = {
                    "status": "failed",
                    "provider_used": "none",
                    "model_used": "none",
                    "warnings": [str(exc)],
                    "attempts": [],
                }

        existing = st.session_state.get("ai_brief", "Press 'Generate executive AI brief' to produce a strategy summary.")
        edited = st.text_area("Executive brief", value=existing, height=340)
        st.session_state["ai_brief"] = edited

        orchestration_view = st.session_state.get("ai_orchestration")
        if orchestration_view:
            with st.expander("LLM orchestration details"):
                st.json(orchestration_view)

    with export_tab:
        st.subheader("Export Package")
        profile_export = pd.DataFrame(analysis["table_profiles"])
        rel_export = pd.DataFrame(analysis["relationships"])
        dict_export = st.session_state.get("dictionary_working", _prepare_dictionary_frame(analysis["dictionary"]))
        if "_row_id" in dict_export.columns:
            dict_export = dict_export.drop(columns=["_row_id"])

        full_export = {
            "generated_at": analysis["generated_at"],
            "source_type": analysis["source_type"],
            "avg_quality_score": analysis["avg_quality_score"],
            "table_profiles": analysis["table_profiles"],
            "relationships": analysis["relationships"],
            "data_dictionary": dict_export.to_dict(orient="records"),
            "dictionary_change_log": st.session_state.get("dictionary_change_log", []),
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
            svg_markup = _extract_svg_from_erd_html(analysis.get("er_html", ""))
            if svg_markup:
                st.download_button(
                    "Download ERD SVG",
                    data=svg_markup.encode("utf-8"),
                    file_name="er_diagram.svg",
                    mime="image/svg+xml",
                    use_container_width=True,
                )
            else:
                st.info("SVG export unavailable for this ERD view.")

        png_bytes = _svg_to_png_bytes(_extract_svg_from_erd_html(analysis.get("er_html", "")))
        if png_bytes:
            st.download_button(
                "Download ERD PNG",
                data=png_bytes,
                file_name="er_diagram.png",
                mime="image/png",
                use_container_width=True,
            )

        pdf_bytes, pdf_error = _build_enterprise_pdf_report(
            analysis=analysis,
            ai_brief=st.session_state.get("ai_brief", ""),
            dictionary_df=dict_export,
            relationship_df=rel_export,
            actor=actor,
        )
        if pdf_bytes:
            st.download_button(
                "Download Executive PDF Report",
                data=pdf_bytes,
                file_name="nexus_executive_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        elif pdf_error:
            st.info(pdf_error)

        st.markdown("**ER Diagram Code To Copy (Mermaid)**")
        st.code(analysis.get("mermaid", ""), language="mermaid")

        st.markdown("---")
        st.subheader("Provision MySQL From Dictionary")
        st.caption("Creates a database and table schema from your edited Data Dictionary.")

        p1, p2 = st.columns(2)
        with p1:
            mysql_host = st.text_input("MySQL host", value="localhost", key="mysql_provision_host")
            mysql_port = st.number_input("MySQL port", min_value=1, max_value=65535, value=3306, key="mysql_provision_port")
            mysql_user = st.text_input("MySQL username", value="root", key="mysql_provision_user")
        with p2:
            mysql_password = st.text_input("MySQL password", type="password", key="mysql_provision_password")
            mysql_database = st.text_input("Target database name", value="nexus_dictionary_db", key="mysql_provision_database")

        mysql_fp = "|".join([mysql_host.strip(), str(int(mysql_port)), mysql_user.strip(), mysql_password, mysql_database.strip()])
        previous_mysql_fp = st.session_state.get("mysql_provision_fingerprint")
        if previous_mysql_fp != mysql_fp:
            st.session_state["mysql_provision_fingerprint"] = mysql_fp
            st.session_state["mysql_provision_connection"] = None

        if st.button("Test MySQL connection", use_container_width=True, key="mysql_provision_test"):
            ok, message = test_mysql_connection(
                host=mysql_host,
                port=int(mysql_port),
                username=mysql_user,
                password=mysql_password,
                database="information_schema",
            )
            st.session_state["mysql_provision_connection"] = {"ok": ok, "message": message}

        mysql_state = st.session_state.get("mysql_provision_connection")
        if mysql_state is None:
            st.info("Test MySQL connection first. Create/Update is enabled only after a successful connection.")
        elif mysql_state.get("ok"):
            st.success(str(mysql_state.get("message", "Connection established.")))
        else:
            st.error(str(mysql_state.get("message", "Connection failed.")))

        can_provision = bool(mysql_state and mysql_state.get("ok"))
        if st.button(
            "Create / Update MySQL schema",
            use_container_width=True,
            key="mysql_provision_submit",
            disabled=not can_provision,
        ):
            ok, message, ddl_statements = provision_mysql_from_dictionary(
                dict_export,
                host=mysql_host,
                port=int(mysql_port),
                username=mysql_user,
                password=mysql_password,
                database=mysql_database,
            )
            if ok:
                st.success(message)
            else:
                st.error(message)

            if ddl_statements:
                st.code("\n\n".join(ddl_statements), language="sql")

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