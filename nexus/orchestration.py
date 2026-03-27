from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .ai import generate_ai_brief


SUPPORTED_TASKS = {"executive_brief"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_provider(provider: Optional[str], default: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in {"ollama", "gemini"}:
        return normalized
    return default


def _validate_analysis_payload(analysis: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []

    required = ["source_type", "table_profiles", "relationships", "avg_quality_score"]
    missing = [key for key in required if key not in analysis]
    if missing:
        warnings.append(f"Analysis payload is missing keys: {', '.join(missing)}")

    if not isinstance(analysis.get("table_profiles", []), list):
        warnings.append("Analysis payload key 'table_profiles' should be a list.")
    if not isinstance(analysis.get("relationships", []), list):
        warnings.append("Analysis payload key 'relationships' should be a list.")

    return warnings


def _deterministic_fallback_brief(analysis: Dict[str, Any], reason: str) -> str:
    table_profiles = analysis.get("table_profiles", []) if isinstance(analysis.get("table_profiles"), list) else []
    relationships = analysis.get("relationships", []) if isinstance(analysis.get("relationships"), list) else []
    avg_quality = _safe_float(analysis.get("avg_quality_score", 0.0), default=0.0)
    source_type = str(analysis.get("source_type", "Unknown"))

    table_count = len(table_profiles)
    rel_count = len(relationships)

    worst_table = None
    if table_profiles:
        worst_table = min(table_profiles, key=lambda item: _safe_float(item.get("quality_score", 0.0), 0.0))

    total_issues = 0
    for profile in table_profiles:
        if isinstance(profile.get("issues"), list):
            total_issues += len(profile.get("issues", []))

    lines = [
        "### Executive Analyst Brief (Deterministic Fallback)",
        "",
        f"AI providers were unavailable or failed. Fallback reason: {reason}",
        "",
        "**Schema Overview**",
        f"- Source type: {source_type}",
        f"- Tables analyzed: {table_count}",
        f"- Relationships inferred: {rel_count}",
        f"- Average quality score: {avg_quality:.2f}%",
        "",
        "**Top Risks**",
    ]

    if worst_table:
        worst_name = str(worst_table.get("table", "unknown_table"))
        worst_score = _safe_float(worst_table.get("quality_score", 0.0), 0.0)
        lines.append(f"- Highest priority table: {worst_name} ({worst_score:.2f}% quality)")
    lines.append(f"- Total detected issues across analyzed tables: {total_issues}")

    lines.extend(
        [
            "",
            "**48-Hour Remediation Plan**",
            "- Triage the lowest-quality tables first and resolve high-nullness fields.",
            "- Validate inferred foreign keys with confidence below 0.80 before enforcing constraints.",
            "- Re-run profiling after fixes and compare quality deltas.",
            "",
            "**30-Day Governance Plan**",
            "- Version the data dictionary and track approval of semantic role changes.",
            "- Add automated health checks for completeness, consistency, and temporal regularity.",
            "- Commit each assessment snapshot to the audit ledger for traceability.",
        ]
    )

    return "\n".join(lines)


def orchestrate_llm_task(
    analysis: Dict[str, Any],
    task: str = "executive_brief",
    provider_preference: str = "ollama",
    fallback_provider: Optional[str] = None,
    ollama_model: str = "llama3:latest",
    ollama_endpoint: str = "http://localhost:11434",
    ollama_api_key: str = "",
    gemini_model: str = "gemini-2.0-flash",
    gemini_api_key: str = "",
    timeout_seconds: int = 120,
    additional_instructions: str = "",
) -> Dict[str, Any]:
    started_at = _utc_now_iso()
    start_perf = time.perf_counter()
    attempts: List[Dict[str, str]] = []
    warnings = _validate_analysis_payload(analysis)

    normalized_task = (task or "").strip().lower() or "executive_brief"
    if normalized_task not in SUPPORTED_TASKS:
        output = _deterministic_fallback_brief(
            analysis,
            reason=f"Unsupported task '{normalized_task}'. Supported tasks: {', '.join(sorted(SUPPORTED_TASKS))}",
        )
        latency_ms = int((time.perf_counter() - start_perf) * 1000)
        return {
            "task": normalized_task,
            "status": "deterministic_fallback",
            "provider_used": "deterministic",
            "model_used": "rule_engine_v1",
            "output": output,
            "attempts": attempts,
            "warnings": warnings,
            "started_at": started_at,
            "finished_at": _utc_now_iso(),
            "latency_ms": latency_ms,
        }

    preferred = _normalize_provider(provider_preference, default="ollama")
    fallback = _normalize_provider(
        fallback_provider,
        default=("gemini" if preferred == "ollama" else "ollama"),
    )

    provider_chain = [preferred]
    if fallback not in provider_chain:
        provider_chain.append(fallback)

    for provider in provider_chain:
        if provider == "gemini" and not gemini_api_key.strip():
            attempts.append(
                {
                    "provider": provider,
                    "model": gemini_model,
                    "status": "skipped",
                    "error": "Gemini API key missing.",
                }
            )
            warnings.append("Gemini was skipped because no API key was supplied.")
            continue

        model = gemini_model if provider == "gemini" else ollama_model
        try:
            output = generate_ai_brief(
                analysis=analysis,
                model=model,
                endpoint=ollama_endpoint,
                provider=provider,
                api_key=gemini_api_key,
                ollama_api_key=ollama_api_key,
                timeout_seconds=timeout_seconds,
                additional_instructions=additional_instructions,
            ).strip()

            if not output:
                raise RuntimeError("LLM returned an empty response.")

            attempts.append(
                {
                    "provider": provider,
                    "model": model,
                    "status": "success",
                    "error": "",
                }
            )

            latency_ms = int((time.perf_counter() - start_perf) * 1000)
            status = "completed" if provider == preferred else "fallback_completed"
            return {
                "task": normalized_task,
                "status": status,
                "provider_used": provider,
                "model_used": model,
                "output": output,
                "attempts": attempts,
                "warnings": warnings,
                "started_at": started_at,
                "finished_at": _utc_now_iso(),
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            attempts.append(
                {
                    "provider": provider,
                    "model": model,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    fallback_reason = "; ".join(
        [f"{entry['provider']}:{entry['status']} ({entry['error']})" for entry in attempts]
    )
    output = _deterministic_fallback_brief(analysis, reason=fallback_reason or "No provider attempts made.")
    warnings.append("All configured LLM providers failed; deterministic fallback summary was used.")

    latency_ms = int((time.perf_counter() - start_perf) * 1000)
    return {
        "task": normalized_task,
        "status": "deterministic_fallback",
        "provider_used": "deterministic",
        "model_used": "rule_engine_v1",
        "output": output,
        "attempts": attempts,
        "warnings": warnings,
        "started_at": started_at,
        "finished_at": _utc_now_iso(),
        "latency_ms": latency_ms,
    }
