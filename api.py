from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict, List, Optional
import uvicorn
import traceback
import sys
from pathlib import Path
import math
import json
import pandas as pd
from pydantic import BaseModel, Field

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent))

from nexus.analysis import run_analysis
from nexus.models import DBConnectionConfig
from nexus.orchestration import orchestrate_llm_task
from nexus.reporting import build_enterprise_pdf_report

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


class ReportPDFRequest(BaseModel):
    analysis: Dict[str, Any] = Field(default_factory=dict)
    ai_brief: str = ""
    report_title: str = "Nexus Intelligence Enterprise Technical Assessment"


def _parse_bool(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on", "y"}


def _clamp_confidence(value: float, default: float = 0.85) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.70, min(0.99, parsed))


def sanitize_for_json(data):
    if isinstance(data, dict):
        return {str(k): sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_for_json(x) for x in data]
    if isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    if hasattr(data, "dtype"):
        return data.item()
    return data


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


@app.post("/api/report/pdf")
async def export_report_pdf(payload: ReportPDFRequest):
    try:
        pdf_bytes = build_enterprise_pdf_report(
            analysis=payload.analysis,
            ai_brief=payload.ai_brief,
            report_title=payload.report_title,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=nexus_enterprise_assessment.pdf"},
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/csv")
async def analyze_csv(
    files: List[UploadFile] = File(...),
    enable_ai_schema_feedback: str = Form("false"),
    ai_schema_feedback_min_confidence: float = Form(0.85),
    ollama_model: str = Form("llama3:latest"),
    ollama_endpoint: str = Form("http://localhost:11434"),
):
    file_map = {}
    for f in files:
        file_map[f.filename] = await f.read()

    schema_feedback_enabled = _parse_bool(enable_ai_schema_feedback)
    confidence_threshold = _clamp_confidence(ai_schema_feedback_min_confidence)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        results = run_analysis(
            source_type="CSV",
            file_map=file_map,
            profile_row_limit=5000,
            db_config=None,
            progress_callback=None,
            erd_layout_direction="TB",
            ollama_model=ollama_model if schema_feedback_enabled else "",
            ollama_endpoint=ollama_endpoint,
            enable_ai_schema_feedback=schema_feedback_enabled,
            ai_schema_feedback_min_confidence=confidence_threshold,
        )

        tables_df = results.pop("tables", {})
        sample_tables = {}
        for table_name, df in tables_df.items():
            try:
                if hasattr(df, "head"):
                    sample_tables[table_name] = json.loads(df.head(50).to_json(orient="records", date_format="iso"))
                else:
                    sample_tables[table_name] = df[:50] if isinstance(df, list) else []
            except Exception:
                sample_tables[table_name] = []
        results["sample_tables"] = sample_tables

        dictionary = results.pop("dictionary", None)

        ai_brief = "AI features bypassed for rapid dev."
        if (OUTPUT_DIR / "ai_brief.txt").exists():
            ai_brief = (OUTPUT_DIR / "ai_brief.txt").read_text(encoding="utf-8")

        return {
            "analysis": sanitize_for_json(results),
            "er_diagram": results.get("mermaid", ""),
            "ai_brief": ai_brief,
            "data_dict": sanitize_for_json(dictionary) if dictionary is not None else [],
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
    enable_ai_schema_feedback: str = Form("false"),
    ai_schema_feedback_min_confidence: float = Form(0.85),
    ollama_model: str = Form("llama3:latest"),
    ollama_endpoint: str = Form("http://localhost:11434"),
):
    config = DBConnectionConfig(
        db_type=db_type,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
    )

    schema_feedback_enabled = _parse_bool(enable_ai_schema_feedback)
    confidence_threshold = _clamp_confidence(ai_schema_feedback_min_confidence)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        results = run_analysis(
            source_type="DB Connection",
            file_map={},
            profile_row_limit=5000,
            db_config=config,
            progress_callback=None,
            ollama_model=ollama_model if schema_feedback_enabled else "",
            ollama_endpoint=ollama_endpoint,
            enable_ai_schema_feedback=schema_feedback_enabled,
            ai_schema_feedback_min_confidence=confidence_threshold,
        )

        tables_df = results.pop("tables", {})
        sample_tables = {}
        for table_name, df in tables_df.items():
            try:
                if hasattr(df, "head"):
                    sample_tables[table_name] = json.loads(df.head(50).to_json(orient="records", date_format="iso"))
                else:
                    sample_tables[table_name] = df[:50] if isinstance(df, list) else []
            except Exception:
                sample_tables[table_name] = []
        results["sample_tables"] = sample_tables

        dictionary = results.pop("dictionary", None)

        ai_brief = "AI features bypassed for rapid dev."
        if (OUTPUT_DIR / "ai_brief.txt").exists():
            ai_brief = (OUTPUT_DIR / "ai_brief.txt").read_text(encoding="utf-8")

        return {
            "analysis": sanitize_for_json(results),
            "er_diagram": results.get("mermaid", ""),
            "ai_brief": ai_brief,
            "data_dict": sanitize_for_json(dictionary) if dictionary is not None else [],
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
