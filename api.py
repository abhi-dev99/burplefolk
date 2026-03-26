from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict, List, Optional
import uvicorn
import traceback
import sys
import os
from pathlib import Path
import math
try:
    import tomllib
except Exception:  # pragma: no cover - fallback for older Python runtimes
    tomllib = None
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent))

from nexus.analysis import run_analysis
from nexus.agent_email import (
    firebase_email_password_login,
    get_event_log,
    process_agent_inbox_once,
)
from nexus.models import DBConnectionConfig
from nexus.orchestration import orchestrate_llm_task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("outputs/api_run")


class LLMOrchestrateRequest(BaseModel):
    analysis: Dict[str, Any] = Field(default_factory=dict)
    task: str = "executive_brief"
    provider_preference: str = "ollama"
    fallback_provider: Optional[str] = None
    ollama_model: str = "llama3:latest"
    ollama_endpoint: str = "http://localhost:11434"
    gemini_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""
    timeout_seconds: int = Field(default=120, ge=30, le=300)


class AgentFirebaseLoginRequest(BaseModel):
    email: str
    password: str
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_project_id: str = ""
    firebase_storage_bucket: str = ""
    firebase_app_id: str = ""


class AgentProcessOnceRequest(BaseModel):
    sample_tables: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    agent_email: str
    gmail_app_password: str
    imap_host: str = "imap.gmail.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    max_messages_per_cycle: int = Field(default=5, ge=1, le=20)
    ai_provider: str = "ollama"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


def _resolve_firebase_config(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    streamlit_secrets = _load_streamlit_secrets()

    data = {
        "firebase_api_key": _first_non_empty(
            os.getenv("FIREBASE_API_KEY", ""),
            str(streamlit_secrets.get("FIREBASE_API_KEY", "")),
        ),
        "firebase_auth_domain": _first_non_empty(
            os.getenv("FIREBASE_AUTH_DOMAIN", ""),
            str(streamlit_secrets.get("FIREBASE_AUTH_DOMAIN", "")),
        ),
        "firebase_project_id": _first_non_empty(
            os.getenv("FIREBASE_PROJECT_ID", ""),
            str(streamlit_secrets.get("FIREBASE_PROJECT_ID", "")),
        ),
        "firebase_storage_bucket": _first_non_empty(
            os.getenv("FIREBASE_STORAGE_BUCKET", ""),
            str(streamlit_secrets.get("FIREBASE_STORAGE_BUCKET", "")),
        ),
        "firebase_app_id": _first_non_empty(
            os.getenv("FIREBASE_APP_ID", ""),
            str(streamlit_secrets.get("FIREBASE_APP_ID", "")),
        ),
    }
    if overrides:
        for key, value in overrides.items():
            if value and str(value).strip():
                data[key] = str(value).strip()
    return data


def _first_non_empty(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _load_streamlit_secrets() -> Dict[str, Any]:
    if tomllib is None:
        return {}

    root = Path(__file__).resolve().parent
    candidates = [
        root / ".streamlit" / "secrets.toml",
        root / ".streamlit" / "secrets.toml.example",
    ]
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            with candidate.open("rb") as f:
                parsed = tomllib.load(f)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return {}

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


def _sample_tables_to_dataframes(sample_tables: Dict[str, List[Dict[str, Any]]]) -> Dict[str, pd.DataFrame]:
    tables: Dict[str, pd.DataFrame] = {}
    for table_name, rows in sample_tables.items():
        if not isinstance(rows, list):
            continue
        try:
            tables[str(table_name)] = pd.DataFrame(rows)
        except Exception:
            continue
    return tables


@app.get("/api/agent/runtime-config")
async def agent_runtime_config():
    firebase_cfg = _resolve_firebase_config()
    streamlit_secrets = _load_streamlit_secrets()
    default_agent_email = _first_non_empty(
        os.getenv("AGENT_DEFAULT_EMAIL", ""),
        str(streamlit_secrets.get("AGENT_DEFAULT_EMAIL", "")),
    )
    default_gmail_app_password = _first_non_empty(
        os.getenv("GMAIL_APP_PASSWORD", ""),
        str(streamlit_secrets.get("AGENT_GMAIL_APP_PASSWORD", "")),
    )
    return {
        "default_agent_email": default_agent_email,
        "default_gmail_app_password": default_gmail_app_password,
        "firebase_config_present": bool(firebase_cfg["firebase_api_key"]),
        "firebase_api_key": firebase_cfg["firebase_api_key"],
        "firebase_auth_domain": firebase_cfg["firebase_auth_domain"],
        "firebase_project_id": firebase_cfg["firebase_project_id"],
        "firebase_storage_bucket": firebase_cfg["firebase_storage_bucket"],
        "firebase_app_id": firebase_cfg["firebase_app_id"],
        "reply_rate_limit_per_minute": 3,
        "agent_policy": {
            "require_direct_to_or_allowed_domain": True,
            "allowed_domain": "burplefolk.com",
            "business_query_only": True,
        },
        "gmail_mode": {
            "firebase_required_for_processing": False,
            "credentials_required": ["agent_email", "gmail_app_password"],
        },
    }


@app.post("/api/agent/firebase-login")
async def agent_firebase_login(payload: AgentFirebaseLoginRequest):
    try:
        firebase_cfg = _resolve_firebase_config(
            {
                "firebase_api_key": payload.firebase_api_key,
                "firebase_auth_domain": payload.firebase_auth_domain,
                "firebase_project_id": payload.firebase_project_id,
                "firebase_storage_bucket": payload.firebase_storage_bucket,
                "firebase_app_id": payload.firebase_app_id,
            }
        )
        ok, msg, user = firebase_email_password_login(
            firebase_api_key=firebase_cfg["firebase_api_key"],
            firebase_auth_domain=firebase_cfg["firebase_auth_domain"],
            firebase_project_id=firebase_cfg["firebase_project_id"],
            firebase_storage_bucket=firebase_cfg["firebase_storage_bucket"],
            email=payload.email,
            password=payload.password,
        )
        return {
            "ok": bool(ok),
            "message": msg,
            "email": payload.email,
            "firebase_config_present": bool(firebase_cfg["firebase_api_key"]),
            "id_token": (user or {}).get("idToken", "") if isinstance(user, dict) else "",
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/ollama-models")
async def agent_ollama_models(endpoint: str = "http://localhost:11434"):
    try:
        from nexus.ai import ollama_get_models

        safe_endpoint = str(endpoint or "http://localhost:11434").strip() or "http://localhost:11434"
        models = ollama_get_models(safe_endpoint)
        return {
            "endpoint": safe_endpoint,
            "models": models,
            "detected": len(models),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/process-once")
async def agent_process_once(payload: AgentProcessOnceRequest):
    try:
        tables = _sample_tables_to_dataframes(payload.sample_tables)
        if not tables:
            raise HTTPException(status_code=400, detail="No sampled tables were supplied for agent query context.")

        summary = process_agent_inbox_once(
            agent_email=payload.agent_email,
            gmail_app_password=payload.gmail_app_password,
            imap_host=payload.imap_host,
            smtp_host=payload.smtp_host,
            smtp_port=payload.smtp_port,
            tables=tables,
            max_messages_per_cycle=payload.max_messages_per_cycle,
            ai_provider=payload.ai_provider,
            ollama_endpoint=payload.ollama_endpoint,
            ollama_model=payload.ollama_model,
            gemini_api_key=payload.gemini_api_key,
            gemini_model=payload.gemini_model,
        )
        return sanitize_for_json(summary)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/events")
async def agent_events(limit: int = 50):
    try:
        safe_limit = max(1, min(200, int(limit)))
        return {"events": sanitize_for_json(get_event_log(limit=safe_limit))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/orchestrate")
async def orchestrate_llm(payload: LLMOrchestrateRequest):
    try:
        result = orchestrate_llm_task(
            analysis=payload.analysis,
            task=payload.task,
            provider_preference=payload.provider_preference,
            fallback_provider=payload.fallback_provider,
            ollama_model=payload.ollama_model,
            ollama_endpoint=payload.ollama_endpoint,
            gemini_model=payload.gemini_model,
            gemini_api_key=payload.gemini_api_key,
            timeout_seconds=payload.timeout_seconds,
        )
        return sanitize_for_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze/csv")
async def analyze_csv(files: List[UploadFile] = File(...)):
    file_map = {}
    for f in files:
        file_map[f.filename] = await f.read()
    
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        results = run_analysis(
            source_type="CSV",
            file_map=file_map,
            profile_row_limit=5000,
            db_config=None,
            progress_callback=None,
            erd_layout_direction="TB",
        )
        
        # Pop pandas df's that crash json
        results.pop('tables', None)
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
        results = run_analysis(
            source_type="DB Connection",
            file_map={},
            profile_row_limit=5000,
            db_config=config,
            progress_callback=None,
        )
        
        results.pop('tables', None)
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

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
