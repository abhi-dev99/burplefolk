from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
import traceback
import sys
from pathlib import Path
import math
import numpy as np
import pandas as pd

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent))

from nexus.analysis import run_analysis
from nexus.models import DBConnectionConfig

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("outputs/api_run")

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
        
        import json
        
        # Calculate exact storage bytes for the overview UI instead of mathematical estimations
        storage_bytes = sum(len(content) for content in file_map.values())
        results["storage_bytes"] = storage_bytes
        
        # Pop pandas df's that crash json
        tables_df = results.pop('tables', {})
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
        
        import json
        tables_df = results.pop('tables', {})
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

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
