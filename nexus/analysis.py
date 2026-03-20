from datetime import datetime, timezone
import html
from typing import Callable, Dict, List, Optional

import numpy as np

from .ai import generate_ai_erd_layout_hints
from .ingestion import csv_ingest, database_ingest, sqlite_ingest
from .models import DBConnectionConfig
from .profiling import build_dictionary, compute_business_context, profile_table
from .schema import infer_foreign_keys, infer_primary_keys
from .visualization import build_erd_html, format_mermaid


def run_analysis(
    source_type: str,
    file_map: Dict[str, bytes],
    profile_row_limit: int,
    db_config: Optional[DBConnectionConfig] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    erd_view_mode: str = "full",
    erd_layout_direction: str = "LR",
    ollama_model: str = "",
    ollama_endpoint: str = "http://localhost:11434",
    enable_ai_erd_fallback: bool = False,
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

    emit(88, "Generating business context and ERD")
    business_context = compute_business_context(table_profiles, merged_relationships)
    mermaid = format_mermaid(table_profiles, merged_relationships, pk_map, view_mode=erd_view_mode)
    erd_renderer = "native"
    erd_fallback_note = ""

    try:
        er_html = build_erd_html(
            table_profiles,
            merged_relationships,
            pk_map,
            view_mode=erd_view_mode,
            layout_direction=erd_layout_direction,
        )
    except Exception as render_exc:
        ai_hints: Dict = {}
        if enable_ai_erd_fallback and ollama_model:
            ai_hints = generate_ai_erd_layout_hints(
                table_profiles,
                merged_relationships,
                model=ollama_model,
                endpoint=ollama_endpoint,
            )

        try:
            er_html = build_erd_html(
                table_profiles,
                merged_relationships,
                pk_map,
                view_mode=erd_view_mode,
                layout_direction=erd_layout_direction,
                table_order_override=ai_hints.get("table_order") if ai_hints else None,
                domain_hints=ai_hints.get("domain_hints") if ai_hints else None,
                fallback_note=(
                    f"Ollama ERD fallback engaged ({ollama_model})."
                    if ai_hints
                    else "Renderer recovered using safe deterministic fallback mode."
                ),
            )
            erd_renderer = "ollama-fallback" if ai_hints else "native-safe-fallback"
            if ai_hints:
                erd_fallback_note = f"Fallback used Ollama model '{ollama_model}' to generate layout hints."
            else:
                erd_fallback_note = "Primary renderer failed; safe deterministic fallback was used."
        except Exception as fallback_exc:
            erd_renderer = "error-safe"
            erd_fallback_note = (
                "ERD renderer failed in both primary and fallback mode. "
                "A safe error panel is shown instead of hanging the UI."
            )
            er_html = (
                "<html><body style=\"margin:0;font-family:Segoe UI,sans-serif;background:#f8fafc;color:#0f172a;\">"
                "<div style=\"padding:16px;border:1px solid #fecaca;background:#fff1f2;border-radius:8px;\">"
                "<h3 style=\"margin:0 0 8px 0;color:#991b1b;\">ER Diagram Rendering Failed</h3>"
                f"<p style=\"margin:0 0 6px 0;\"><strong>Primary:</strong> {html.escape(str(render_exc))}</p>"
                f"<p style=\"margin:0;\"><strong>Fallback:</strong> {html.escape(str(fallback_exc))}</p>"
                "</div></body></html>"
            )

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
        "mermaid": mermaid,
        "erd_renderer": erd_renderer,
        "erd_fallback_note": erd_fallback_note,
    }
