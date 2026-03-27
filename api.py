from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import uvicorn
import traceback
import sys
from pathlib import Path
import math
import os
import threading
import tomllib
import numpy as np
import pandas as pd

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent))

from nexus.analysis import run_analysis
from nexus.ai import ollama_get_models
from nexus.agent_email import (
    AgentLoopConfig,
    firebase_email_password_login,
    get_event_log,
    process_agent_inbox_once,
    run_agent_inbox_loop,
)
from nexus.models import DBConnectionConfig

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("outputs/api_run")
SECRETS_FILE = Path(".streamlit/secrets.toml")
_LATEST_TABLES: Dict[str, pd.DataFrame] = {}
_LATEST_TABLES_LOCK = threading.Lock()
_AGENT_LOOP_LOCK = threading.Lock()
_AGENT_LOOP_THREAD: Optional[threading.Thread] = None
_AGENT_LOOP_STOP_EVENT: Optional[threading.Event] = None
_AGENT_LOOP_FINGERPRINT: str = ""
_AGENT_LOOP_META: Dict[str, Any] = {}
_MIN_AGENT_POLL_SECONDS = 5
_MAX_AGENT_POLL_SECONDS = 60
_MIN_AGENT_MESSAGES_PER_CYCLE = 0
_MAX_AGENT_MESSAGES_PER_CYCLE = 5


class AgentLoginRequest(BaseModel):
    firebase_api_key: str
    firebase_auth_domain: str
    firebase_project_id: str
    firebase_storage_bucket: str
    email: str
    password: str


class AgentProcessRequest(BaseModel):
    agent_email: str
    gmail_app_password: str
    imap_host: str = "imap.gmail.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    max_messages_per_cycle: int = 5
    ai_provider: str = "ollama"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


class AgentAutoReplyRequest(BaseModel):
    enable_auto_reply: bool
    poll_seconds: int = _MIN_AGENT_POLL_SECONDS
    agent_email: str
    gmail_app_password: str
    imap_host: str = "imap.gmail.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    max_messages_per_cycle: int = 5
    ai_provider: str = "ollama"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


def _load_streamlit_secrets() -> Dict[str, Any]:
    if not SECRETS_FILE.exists():
        return {}
    try:
        with SECRETS_FILE.open("rb") as fh:
            parsed = tomllib.load(fh)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _cfg_value(name: str, default: str = "") -> str:
    env_value = os.getenv(name)
    if env_value:
        return str(env_value)
    secrets = _load_streamlit_secrets()
    value = secrets.get(name, default)
    if value is None:
        return default
    return str(value)


def _set_latest_tables(tables: Dict[str, Any]) -> None:
    normalized: Dict[str, pd.DataFrame] = {}
    for name, frame in tables.items():
        if isinstance(frame, pd.DataFrame):
            normalized[str(name)] = frame.copy()
    with _LATEST_TABLES_LOCK:
        _LATEST_TABLES.clear()
        _LATEST_TABLES.update(normalized)


def _get_latest_tables_snapshot() -> Dict[str, pd.DataFrame]:
    with _LATEST_TABLES_LOCK:
        return {name: frame.copy() for name, frame in _LATEST_TABLES.items()}


def _agent_loop_status_locked() -> Dict[str, Any]:
    alive = bool(_AGENT_LOOP_THREAD is not None and _AGENT_LOOP_THREAD.is_alive())
    return {
        "running": alive,
        "live": alive,
        "meta": _AGENT_LOOP_META,
    }


def _agent_loop_status() -> Dict[str, Any]:
    with _AGENT_LOOP_LOCK:
        return _agent_loop_status_locked()


def _stop_agent_loop_locked() -> None:
    global _AGENT_LOOP_THREAD, _AGENT_LOOP_STOP_EVENT, _AGENT_LOOP_FINGERPRINT, _AGENT_LOOP_META
    if _AGENT_LOOP_STOP_EVENT is not None:
        _AGENT_LOOP_STOP_EVENT.set()
    _AGENT_LOOP_THREAD = None
    _AGENT_LOOP_STOP_EVENT = None
    _AGENT_LOOP_FINGERPRINT = ""
    _AGENT_LOOP_META = {}


def _resolve_profile_row_limit(raw_limit: Optional[int]) -> int:
    """
    Normalize row-limit input.
    - 0 means full scan (no row cap).
    - Positive values are clamped to a safe upper bound.
    """
    if raw_limit is None:
        return 1000000
    try:
        value = int(raw_limit)
    except (TypeError, ValueError):
        return 1000000
    if value <= 0:
        return 0
    return min(value, 2000000)


def _normalize_agent_poll_seconds(raw_seconds: int) -> int:
    try:
        value = int(raw_seconds)
    except (TypeError, ValueError):
        return _MIN_AGENT_POLL_SECONDS
    return max(_MIN_AGENT_POLL_SECONDS, min(_MAX_AGENT_POLL_SECONDS, value))


def _normalize_agent_messages_per_cycle(raw_count: int) -> int:
    try:
        value = int(raw_count)
    except (TypeError, ValueError):
        return _MAX_AGENT_MESSAGES_PER_CYCLE
    return max(_MIN_AGENT_MESSAGES_PER_CYCLE, min(_MAX_AGENT_MESSAGES_PER_CYCLE, value))

def sanitize_for_json(data):
    if isinstance(data, dict):
        return {str(k): sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(x) for x in data]
    elif isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif hasattr(data, 'dtype'):
        return data.item()
    return data

@app.post("/api/analyze/csv")
async def analyze_csv(
    files: List[UploadFile] = File(...),
    profile_row_limit: int = Form(1000000),
):
    file_map = {}
    for f in files:
        file_map[f.filename] = await f.read()
    
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        resolved_profile_limit = _resolve_profile_row_limit(profile_row_limit)
        results = run_analysis(
            source_type="CSV",
            file_map=file_map,
            profile_row_limit=resolved_profile_limit,
            db_config=None,
            progress_callback=None,
            erd_layout_direction="TB",
        )
        
        import json
        # Pop pandas df's that crash json
        tables_df = results.pop('tables', {})
        _set_latest_tables(tables_df)
        sample_tables = {}
        for t_name, df in tables_df.items():
            try:
                if hasattr(df, 'head'):
                    sample_tables[t_name] = json.loads(df.head(50).to_json(orient="records", date_format="iso"))
                else:
                    sample_tables[t_name] = df[:50] if isinstance(df, list) else []
            except Exception:
                sample_tables[t_name] = []
        results["sample_tables"] = sample_tables
        
        dictionary = results.pop('dictionary', None)
        
        ai_brief = "AI features bypassed for rapid dev."
        if (OUTPUT_DIR / "ai_brief.txt").exists():
            ai_brief = (OUTPUT_DIR / "ai_brief.txt").read_text()

        # The ER diagram is generated internally as mermaid:
        return {
            "analysis": sanitize_for_json(results),
            "er_diagram": results.get("mermaid", ""),
            "ai_brief": ai_brief,
            "data_dict": sanitize_for_json(dictionary) if dictionary is not None else []
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze/db")
async def analyze_db(
    db_type: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    database: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    profile_row_limit: int = Form(1000000),
):
    config = DBConnectionConfig(
        db_type=db_type,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password
    )
    
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        resolved_profile_limit = _resolve_profile_row_limit(profile_row_limit)
        results = run_analysis(
            source_type="DB Connection",
            file_map={},
            profile_row_limit=resolved_profile_limit,
            db_config=config,
            progress_callback=None,
        )
        
        import json
        tables_df = results.pop('tables', {})
        _set_latest_tables(tables_df)
        sample_tables = {}
        for t_name, df in tables_df.items():
            try:
                if hasattr(df, 'head'):
                    sample_tables[t_name] = json.loads(df.head(50).to_json(orient="records", date_format="iso"))
                else:
                    sample_tables[t_name] = df[:50] if isinstance(df, list) else []
            except Exception:
                sample_tables[t_name] = []
        results["sample_tables"] = sample_tables
        
        dictionary = results.pop('dictionary', None)
        
        ai_brief = "AI features bypassed for rapid dev."
        if (OUTPUT_DIR / "ai_brief.txt").exists():
            ai_brief = (OUTPUT_DIR / "ai_brief.txt").read_text()

        return {
            "analysis": sanitize_for_json(results),
            "er_diagram": results.get("mermaid", ""),
            "ai_brief": ai_brief,
            "data_dict": sanitize_for_json(dictionary) if dictionary is not None else []
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/defaults")
async def agent_defaults():
    endpoint = "http://localhost:11434"
    models: List[str] = []
    try:
        models = ollama_get_models(endpoint)
    except Exception:
        models = []

    return {
        "firebase": {
            "apiKey": _cfg_value("FIREBASE_API_KEY", ""),
            "authDomain": _cfg_value("FIREBASE_AUTH_DOMAIN", ""),
            "projectId": _cfg_value("FIREBASE_PROJECT_ID", ""),
            "storageBucket": _cfg_value("FIREBASE_STORAGE_BUCKET", ""),
        },
        "defaultAgentEmail": _cfg_value("AGENT_DEFAULT_EMAIL", "burplefolk@gmail.com"),
        "imapHost": "imap.gmail.com",
        "smtpHost": "smtp.gmail.com",
        "smtpPort": 587,
        "pollSeconds": _MIN_AGENT_POLL_SECONDS,
        "maxMessagesPerCycle": 5,
        "aiProvider": "ollama",
        "ollamaEndpoint": endpoint,
        "ollamaModels": models,
        "ollamaModel": models[0] if models else "llama2",
        "geminiModel": "gemini-2.0-flash",
    }


@app.get("/api/agent/ollama-models")
async def agent_ollama_models(endpoint: str = "http://localhost:11434"):
    try:
        models = ollama_get_models(endpoint)
        return {"models": models}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to fetch Ollama models: {exc}")


@app.post("/api/agent/login")
async def agent_login(payload: AgentLoginRequest):
    ok, message, user = firebase_email_password_login(
        firebase_api_key=payload.firebase_api_key,
        firebase_auth_domain=payload.firebase_auth_domain,
        firebase_project_id=payload.firebase_project_id,
        firebase_storage_bucket=payload.firebase_storage_bucket,
        email=payload.email,
        password=payload.password,
    )
    return {
        "ok": ok,
        "message": message,
        "email": payload.email,
        "idToken": str((user or {}).get("idToken", "")) if ok else "",
    }


@app.post("/api/agent/process-once")
async def agent_process_once(payload: AgentProcessRequest):
    tables_snapshot = _get_latest_tables_snapshot()
    if not tables_snapshot:
        raise HTTPException(status_code=400, detail="No analyzed tables are available yet. Analyze data first.")

    try:
        normalized_max_messages = _normalize_agent_messages_per_cycle(payload.max_messages_per_cycle)
        summary = process_agent_inbox_once(
            agent_email=payload.agent_email,
            gmail_app_password=payload.gmail_app_password,
            imap_host=payload.imap_host,
            smtp_host=payload.smtp_host,
            smtp_port=int(payload.smtp_port),
            tables=tables_snapshot,
            max_messages_per_cycle=normalized_max_messages,
            ai_provider=payload.ai_provider,
            ollama_endpoint=payload.ollama_endpoint,
            ollama_model=payload.ollama_model,
            gemini_api_key=payload.gemini_api_key,
            gemini_model=payload.gemini_model,
        )
        return {"ok": True, "summary": sanitize_for_json(summary)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent inbox processing failed: {exc}")


@app.get("/api/agent/logs")
async def agent_logs(limit: int = 50):
    safe_limit = max(1, min(int(limit), 200))
    return {"events": sanitize_for_json(get_event_log(limit=safe_limit))}


@app.post("/api/agent/auto-reply")
async def agent_auto_reply(payload: AgentAutoReplyRequest):
    tables_snapshot = _get_latest_tables_snapshot()
    if payload.enable_auto_reply and not tables_snapshot:
        raise HTTPException(status_code=400, detail="No analyzed tables are available yet. Analyze data first.")

    snapshot_signature = ",".join(sorted(tables_snapshot.keys())) if tables_snapshot else ""
    normalized_poll_seconds = _normalize_agent_poll_seconds(payload.poll_seconds)
    normalized_max_messages = _normalize_agent_messages_per_cycle(payload.max_messages_per_cycle)
    fingerprint = "|".join(
        [
            snapshot_signature,
            payload.agent_email.strip(),
            payload.imap_host.strip(),
            payload.smtp_host.strip(),
            str(int(payload.smtp_port)),
            str(normalized_poll_seconds),
            str(normalized_max_messages),
            payload.ai_provider,
            payload.ollama_endpoint.strip(),
            payload.ollama_model.strip(),
            payload.gemini_model.strip(),
            "enabled" if payload.enable_auto_reply else "disabled",
        ]
    )

    global _AGENT_LOOP_THREAD, _AGENT_LOOP_STOP_EVENT, _AGENT_LOOP_FINGERPRINT, _AGENT_LOOP_META
    with _AGENT_LOOP_LOCK:
        if not payload.enable_auto_reply:
            _stop_agent_loop_locked()
            return {"ok": True, "status": _agent_loop_status_locked()}

        is_alive = bool(_AGENT_LOOP_THREAD is not None and _AGENT_LOOP_THREAD.is_alive())
        if is_alive and _AGENT_LOOP_FINGERPRINT == fingerprint:
            return {"ok": True, "status": _agent_loop_status_locked()}

        _stop_agent_loop_locked()
        stop_event = threading.Event()
        loop_config = AgentLoopConfig(
            agent_email=payload.agent_email,
            gmail_app_password=payload.gmail_app_password,
            imap_host=payload.imap_host,
            smtp_host=payload.smtp_host,
            smtp_port=int(payload.smtp_port),
            interval_seconds=normalized_poll_seconds,
            max_messages_per_cycle=normalized_max_messages,
            ai_provider=payload.ai_provider,
            ollama_endpoint=payload.ollama_endpoint,
            ollama_model=payload.ollama_model,
            gemini_api_key=payload.gemini_api_key,
            gemini_model=payload.gemini_model,
        )
        loop_thread = threading.Thread(
            target=run_agent_inbox_loop,
            args=(stop_event, loop_config, tables_snapshot),
            daemon=True,
            name="agent-auto-reply-loop",
        )
        loop_thread.start()

        _AGENT_LOOP_THREAD = loop_thread
        _AGENT_LOOP_STOP_EVENT = stop_event
        _AGENT_LOOP_FINGERPRINT = fingerprint
        _AGENT_LOOP_META = {
            "agent_email": payload.agent_email,
            "poll_seconds": normalized_poll_seconds,
            "max_messages_per_cycle": normalized_max_messages,
            "ai_provider": payload.ai_provider,
            "sla_deadline_seconds": _MAX_AGENT_POLL_SECONDS,
        }

        return {"ok": True, "status": _agent_loop_status_locked()}


@app.get("/api/agent/auto-reply/status")
async def agent_auto_reply_status():
    return _agent_loop_status()

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
