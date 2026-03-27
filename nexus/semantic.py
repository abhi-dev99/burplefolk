import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


SEMANTIC_CONFIG_FILE = Path("semantic_layer.json")
SEMANTIC_HISTORY_FILE = Path("outputs/semantic_history.jsonl")

_DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "entities": [
        {"name": "customer", "aliases": ["customer", "customers", "client", "buyer"]},
        {"name": "order", "aliases": ["order", "orders", "purchase", "transaction"]},
        {"name": "product", "aliases": ["product", "products", "item", "sku"]},
        {"name": "payment", "aliases": ["payment", "payments", "invoice", "billing"]},
        {"name": "seller", "aliases": ["seller", "merchant", "vendor", "supplier"]},
    ],
    "role_synonyms": {
        "business_key": ["id", "_id", "code", "key", "uuid"],
        "foreign_key": ["*_id", "*_code", "*_key", "ref", "reference"],
        "measure": ["amount", "price", "cost", "revenue", "total", "value", "qty", "quantity"],
        "event_time": ["date", "time", "timestamp", "created", "updated", "occurred"],
        "status": ["status", "state", "type", "stage"],
        "pii": ["email", "phone", "mobile", "ssn", "aadhaar", "pan", "passport"],
        "descriptor": ["name", "title", "description", "desc", "comment", "review", "text"],
    },
    "column_overrides": {
        # Example:
        # "orders.customer_id": {
        #   "role": "foreign_key",
        #   "entity": "customer",
        #   "canonical_name": "customer_id",
        #   "business_term": "Customer Identifier"
        # }
    },
    "metrics": [
        {"name": "row_count", "kind": "count_rows"},
        {"name": "total_revenue", "kind": "sum", "column_hints": ["amount", "total", "revenue", "price"]},
        {
            "name": "null_ratio",
            "kind": "ratio",
            "numerator": "null_cells",
            "denominator": "total_cells",
        },
    ],
    "constraints": [
        {
            "name": "business_keys_should_not_be_null",
            "type": "role_null_threshold",
            "role": "business_key",
            "max_null_percent": 5.0,
        },
        {
            "name": "event_time_should_exist",
            "type": "role_presence",
            "role": "event_time",
            "min_columns": 1,
        },
        {
            "name": "email_columns_should_match_email_pattern",
            "type": "column_regex",
            "table_pattern": "*",
            "column_pattern": "*email*",
            "regex": r"^[\\w\\.-]+@[\\w\\.-]+\\.[A-Za-z]{2,}$",
            "max_mismatch_percent": 20.0,
        },
        {
            "name": "status_columns_should_use_known_states",
            "type": "allowed_values",
            "table_pattern": "*",
            "column_pattern": "*status*",
            "values": ["pending", "placed", "shipped", "delivered", "cancelled", "active", "inactive"],
            "max_invalid_percent": 40.0,
        },
    ],
}


def _normalize_token(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


def _tokens(value: str) -> List[str]:
    normalized = _normalize_token(value)
    if not normalized:
        return []
    return [tok for tok in normalized.split("_") if tok]


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_default_semantic_config() -> Dict[str, Any]:
    return json.loads(json.dumps(_DEFAULT_CONFIG))


def load_semantic_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = config_path or SEMANTIC_CONFIG_FILE
    config = get_default_semantic_config()
    if not path.exists():
        return config

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return config

    if not isinstance(loaded, dict):
        return config

    return _deep_merge(config, loaded)


def save_semantic_config(config: Dict[str, Any], config_path: Optional[Path] = None) -> None:
    path = config_path or SEMANTIC_CONFIG_FILE
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def validate_semantic_config(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(config, dict):
        return ["Semantic config must be a JSON object."]

    if not isinstance(config.get("entities", []), list):
        errors.append("'entities' must be a list.")
    if not isinstance(config.get("role_synonyms", {}), dict):
        errors.append("'role_synonyms' must be an object.")
    if not isinstance(config.get("column_overrides", {}), dict):
        errors.append("'column_overrides' must be an object.")
    if not isinstance(config.get("metrics", []), list):
        errors.append("'metrics' must be a list.")
    if not isinstance(config.get("constraints", []), list):
        errors.append("'constraints' must be a list.")

    allowed_roles = {
        "business_key",
        "foreign_key",
        "measure",
        "event_time",
        "status",
        "pii",
        "descriptor",
        "attribute",
    }
    for dotted, rule in config.get("column_overrides", {}).items():
        if not isinstance(dotted, str) or "." not in dotted:
            errors.append(f"column_overrides key '{dotted}' must be in 'table.column' format.")
            continue
        role = str(rule.get("role", "")).strip()
        if role and role not in allowed_roles:
            errors.append(f"column_overrides['{dotted}'].role '{role}' is not supported.")

    return errors


def infer_table_entity(table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    table_norm = _normalize_token(table_name)
    table_tokens = set(_tokens(table_name))
    best_entity = "unknown"
    best_score = 0.0

    for entity_def in config.get("entities", []):
        entity_name = str(entity_def.get("name", "")).strip().lower()
        aliases = [entity_name] + [str(a).lower() for a in entity_def.get("aliases", [])]
        for alias in aliases:
            alias_norm = _normalize_token(alias)
            if not alias_norm:
                continue
            score = 0.0
            if table_norm == alias_norm:
                score = 1.0
            elif alias_norm in table_norm:
                score = 0.82
            elif alias_norm in table_tokens:
                score = 0.9
            elif any(tok == alias_norm for tok in table_tokens):
                score = 0.88

            if score > best_score:
                best_score = score
                best_entity = entity_name or "unknown"

    source = "semantic-entity-map" if best_score >= 0.82 else "heuristic"
    return {
        "table": table_name,
        "entity": best_entity,
        "confidence": round(float(best_score), 3),
        "source": source,
    }


def _matches_pattern(name: str, pattern: str) -> bool:
    name_norm = _normalize_token(name)
    pat = str(pattern or "").strip().lower()
    if not pat:
        return False

    if "*" in pat:
        rx = "^" + re.escape(_normalize_token(pat)).replace("\\*", ".*") + "$"
        return bool(re.match(rx, name_norm))

    pat_norm = _normalize_token(pat)
    return bool(pat_norm and (pat_norm in name_norm or name_norm == pat_norm))


def resolve_semantic_role(
    table_name: str,
    column_name: str,
    sample_dtype: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    dotted = f"{_normalize_token(table_name)}.{_normalize_token(column_name)}"
    overrides = config.get("column_overrides", {})

    if dotted in overrides and isinstance(overrides[dotted], dict):
        ov = overrides[dotted]
        return {
            "role": str(ov.get("role", "attribute")),
            "confidence": 1.0,
            "source": "override",
            "canonical_name": str(ov.get("canonical_name") or _normalize_token(column_name)),
            "business_term": str(ov.get("business_term") or column_name),
            "entity": str(ov.get("entity") or infer_table_entity(table_name, config).get("entity", "unknown")),
            "explanation": f"Explicit semantic override found for {dotted}.",
            "candidates": [{"role": str(ov.get("role", "attribute")), "score": 1.0, "reason": "override"}],
        }

    col_norm = _normalize_token(column_name)
    role_scores: Dict[str, float] = {"attribute": 0.25}
    role_reasons: Dict[str, str] = {"attribute": "fallback default"}
    best_role = "attribute"
    best_score = role_scores["attribute"]
    best_source = "heuristic"

    for role, patterns in config.get("role_synonyms", {}).items():
        for pattern in patterns if isinstance(patterns, list) else []:
            if _matches_pattern(col_norm, str(pattern)):
                score = 0.78
                if col_norm == _normalize_token(str(pattern)):
                    score = 0.9
                if score > role_scores.get(role, 0.0):
                    role_scores[role] = score
                    role_reasons[role] = f"matched semantic pattern '{pattern}'"
                if score > best_score:
                    best_score = score
                    best_role = role
                    best_source = "semantic-synonym"

    # Type-aware refinements
    dtype = str(sample_dtype).lower()
    if best_role == "attribute":
        if any(tok in col_norm for tok in ["id", "key", "code", "uuid"]):
            best_role = "business_key"
            best_score = max(best_score, 0.72)
            best_source = "heuristic"
            role_scores["business_key"] = max(role_scores.get("business_key", 0.0), best_score)
            role_reasons["business_key"] = "identifier-like token detected"
        elif any(tok in col_norm for tok in ["date", "time", "timestamp", "created", "updated"]):
            best_role = "event_time"
            best_score = max(best_score, 0.74)
            best_source = "heuristic"
            role_scores["event_time"] = max(role_scores.get("event_time", 0.0), best_score)
            role_reasons["event_time"] = "temporal token detected"
        elif any(tok in col_norm for tok in ["amount", "price", "cost", "value", "qty", "count", "total"]):
            best_role = "measure"
            best_score = max(best_score, 0.73)
            best_source = "heuristic"
            role_scores["measure"] = max(role_scores.get("measure", 0.0), best_score)
            role_reasons["measure"] = "measure token detected"
        elif any(tok in col_norm for tok in ["name", "title", "desc", "comment", "review"]):
            best_role = "descriptor"
            best_score = max(best_score, 0.71)
            best_source = "heuristic"
            role_scores["descriptor"] = max(role_scores.get("descriptor", 0.0), best_score)
            role_reasons["descriptor"] = "descriptor token detected"

    if best_role == "measure" and ("int" in dtype or "float" in dtype or "decimal" in dtype):
        best_score = min(1.0, best_score + 0.05)
        role_scores["measure"] = max(role_scores.get("measure", 0.0), best_score)
        role_reasons["measure"] = "numeric dtype supports measure role"
    if best_role == "event_time" and ("date" in dtype or "time" in dtype):
        best_score = min(1.0, best_score + 0.06)
        role_scores["event_time"] = max(role_scores.get("event_time", 0.0), best_score)
        role_reasons["event_time"] = "datetime dtype supports event_time role"

    canonical_name = col_norm
    entity = infer_table_entity(table_name, config).get("entity", "unknown")
    business_term = column_name.replace("_", " ").strip().title()
    candidate_rows = sorted(role_scores.items(), key=lambda item: item[1], reverse=True)[:3]
    explanation = role_reasons.get(best_role, "best available semantic candidate")

    return {
        "role": best_role,
        "confidence": round(float(best_score), 3),
        "source": best_source,
        "canonical_name": canonical_name,
        "business_term": business_term,
        "entity": entity,
        "explanation": explanation,
        "candidates": [
            {"role": role, "score": round(float(score), 3), "reason": role_reasons.get(role, "candidate")}
            for role, score in candidate_rows
        ],
    }


def semantic_relationship_adjustment(
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
    config: Dict[str, Any],
    child_dtype: str = "",
    parent_dtype: str = "",
) -> float:
    child_meta = resolve_semantic_role(child_table, child_column, child_dtype, config)
    parent_meta = resolve_semantic_role(parent_table, parent_column, parent_dtype, config)

    adjustment = 0.0
    if child_meta["role"] in {"foreign_key", "business_key"} and parent_meta["role"] in {"business_key", "foreign_key"}:
        adjustment += 0.08
    if child_meta.get("entity") and parent_meta.get("entity") and child_meta.get("entity") == parent_meta.get("entity"):
        adjustment += 0.06
    if child_meta["role"] == "measure" or parent_meta["role"] == "measure":
        adjustment -= 0.12
    if child_meta["role"] == "event_time" or parent_meta["role"] == "event_time":
        adjustment -= 0.05

    return float(max(-0.2, min(0.2, adjustment)))


def evaluate_semantic_constraints(
    table_profiles: List[Dict[str, Any]],
    config: Dict[str, Any],
    tables: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []

    for constraint in config.get("constraints", []):
        c_type = str(constraint.get("type", "")).strip()
        c_name = str(constraint.get("name", c_type or "constraint"))

        if c_type == "role_presence":
            role = str(constraint.get("role", "")).strip()
            min_columns = int(constraint.get("min_columns", 1))
            total = 0
            for profile in table_profiles:
                for cp in profile.get("column_profiles", []):
                    if str(cp.get("semantic_role", "")) == role:
                        total += 1
            if total < min_columns:
                violations.append(
                    {
                        "constraint": c_name,
                        "severity": "warning",
                        "message": f"Role '{role}' appears in {total} columns, below required minimum {min_columns}.",
                    }
                )

        elif c_type == "role_null_threshold":
            role = str(constraint.get("role", "")).strip()
            max_null = float(constraint.get("max_null_percent", 100.0))
            for profile in table_profiles:
                table = str(profile.get("table", ""))
                for cp in profile.get("column_profiles", []):
                    if str(cp.get("semantic_role", "")) != role:
                        continue
                    null_percent = float(cp.get("null_percent", 0.0) or 0.0)
                    if null_percent > max_null:
                        violations.append(
                            {
                                "constraint": c_name,
                                "severity": "high",
                                "message": (
                                    f"{table}.{cp.get('column')} has {null_percent:.2f}% nulls "
                                    f"for role '{role}' (max {max_null:.2f}%)."
                                ),
                            }
                        )

        elif c_type == "allowed_values" and tables:
            table_pattern = str(constraint.get("table_pattern", "*")).strip()
            column_pattern = str(constraint.get("column_pattern", "*")).strip()
            allowed = set(str(v) for v in constraint.get("values", []) if str(v).strip())
            if not allowed:
                continue
            max_invalid_percent = float(constraint.get("max_invalid_percent", 0.0))
            for table_name, df in tables.items():
                if not _matches_pattern(table_name, table_pattern):
                    continue
                for col in df.columns:
                    if not _matches_pattern(str(col), column_pattern):
                        continue
                    series = df[col].dropna().astype(str)
                    if series.empty:
                        continue
                    invalid_ratio = float((~series.isin(allowed)).sum()) / float(len(series)) * 100.0
                    if invalid_ratio > max_invalid_percent:
                        violations.append(
                            {
                                "constraint": c_name,
                                "severity": "high",
                                "message": (
                                    f"{table_name}.{col} invalid value ratio {invalid_ratio:.2f}% exceeds "
                                    f"allowed {max_invalid_percent:.2f}%."
                                ),
                            }
                        )

        elif c_type == "column_regex" and tables:
            table_pattern = str(constraint.get("table_pattern", "*")).strip()
            column_pattern = str(constraint.get("column_pattern", "*")).strip()
            regex = str(constraint.get("regex", "")).strip()
            if not regex:
                continue
            try:
                compiled = re.compile(regex)
            except re.error:
                violations.append(
                    {
                        "constraint": c_name,
                        "severity": "warning",
                        "message": f"Invalid regex in semantic constraint: {regex}",
                    }
                )
                continue
            max_mismatch_percent = float(constraint.get("max_mismatch_percent", 0.0))
            for table_name, df in tables.items():
                if not _matches_pattern(table_name, table_pattern):
                    continue
                for col in df.columns:
                    if not _matches_pattern(str(col), column_pattern):
                        continue
                    series = df[col].dropna().astype(str)
                    if series.empty:
                        continue
                    mismatch_ratio = float((~series.str.match(compiled)).sum()) / float(len(series)) * 100.0
                    if mismatch_ratio > max_mismatch_percent:
                        violations.append(
                            {
                                "constraint": c_name,
                                "severity": "high",
                                "message": (
                                    f"{table_name}.{col} regex mismatch {mismatch_ratio:.2f}% exceeds "
                                    f"allowed {max_mismatch_percent:.2f}%."
                                ),
                            }
                        )

        elif c_type == "column_range" and tables:
            table_pattern = str(constraint.get("table_pattern", "*")).strip()
            column_pattern = str(constraint.get("column_pattern", "*")).strip()
            min_value = constraint.get("min")
            max_value = constraint.get("max")
            max_out_of_range_percent = float(constraint.get("max_out_of_range_percent", 0.0))
            for table_name, df in tables.items():
                if not _matches_pattern(table_name, table_pattern):
                    continue
                for col in df.columns:
                    if not _matches_pattern(str(col), column_pattern):
                        continue
                    series = pd.to_numeric(df[col], errors="coerce").dropna()
                    if series.empty:
                        continue
                    mask = pd.Series(False, index=series.index)
                    if min_value is not None:
                        mask = mask | (series < float(min_value))
                    if max_value is not None:
                        mask = mask | (series > float(max_value))
                    out_ratio = float(mask.sum()) / float(len(series)) * 100.0
                    if out_ratio > max_out_of_range_percent:
                        violations.append(
                            {
                                "constraint": c_name,
                                "severity": "high",
                                "message": (
                                    f"{table_name}.{col} out-of-range ratio {out_ratio:.2f}% exceeds "
                                    f"allowed {max_out_of_range_percent:.2f}%"
                                ),
                            }
                        )

    return violations


def compute_semantic_metrics(tables: Dict[str, pd.DataFrame], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    total_rows = sum(int(len(df)) for df in tables.values())
    total_cells = sum(int(df.shape[0] * df.shape[1]) for df in tables.values())
    null_cells = sum(int(df.isna().sum().sum()) for df in tables.values())

    for metric in config.get("metrics", []):
        if not isinstance(metric, dict):
            continue
        name = str(metric.get("name", "metric")).strip()
        kind = str(metric.get("kind", "")).strip().lower()

        value: Optional[float] = None
        status = "ok"
        note = ""

        if kind == "count_rows":
            value = float(total_rows)
        elif kind == "sum":
            hints = [str(h).lower() for h in metric.get("column_hints", [])]
            aggregated = 0.0
            found = 0
            for _, df in tables.items():
                for col in df.columns:
                    col_norm = _normalize_token(col)
                    if hints and not any(h in col_norm for h in hints):
                        continue
                    series = pd.to_numeric(df[col], errors="coerce").dropna()
                    if series.empty:
                        continue
                    aggregated += float(series.sum())
                    found += 1
            value = float(aggregated)
            if found == 0:
                status = "warning"
                note = "No matching numeric columns found for metric hints."
        elif kind == "ratio":
            numerator_key = str(metric.get("numerator", "")).strip().lower()
            denominator_key = str(metric.get("denominator", "")).strip().lower()
            lookups = {
                "total_rows": float(total_rows),
                "total_cells": float(total_cells),
                "null_cells": float(null_cells),
            }
            numerator = lookups.get(numerator_key)
            denominator = lookups.get(denominator_key)
            if numerator is None or denominator is None or denominator == 0:
                status = "warning"
                note = "Ratio metric references unsupported numerator/denominator or zero denominator."
                value = None
            else:
                value = float(numerator / denominator)
        else:
            status = "warning"
            note = f"Unsupported metric kind '{kind}'."

        results.append(
            {
                "name": name,
                "kind": kind,
                "value": round(value, 6) if isinstance(value, (float, int)) else None,
                "status": status,
                "note": note,
            }
        )

    return results


def suggest_semantic_mappings(tables: Dict[str, pd.DataFrame], config: Dict[str, Any]) -> Dict[str, Any]:
    suggestions: List[Dict[str, Any]] = []
    for table_name, df in tables.items():
        entity = infer_table_entity(table_name, config)
        for col in df.columns:
            details = resolve_semantic_role(table_name, str(col), str(df[col].dtype), config)
            suggestions.append(
                {
                    "table": table_name,
                    "column": str(col),
                    "entity": details.get("entity", entity.get("entity", "unknown")),
                    "suggested_role": details.get("role", "attribute"),
                    "confidence": details.get("confidence", 0.0),
                    "source": details.get("source", "heuristic"),
                    "canonical_name": details.get("canonical_name", _normalize_token(str(col))),
                    "business_term": details.get("business_term", str(col)),
                    "explanation": details.get("explanation", ""),
                    "candidates": details.get("candidates", []),
                }
            )

    coverage = float(np.mean([s.get("confidence", 0.0) for s in suggestions])) if suggestions else 0.0
    return {
        "suggestions": sorted(suggestions, key=lambda x: float(x.get("confidence", 0.0)), reverse=True),
        "average_confidence": round(coverage, 4),
        "total_columns": len(suggestions),
    }


def build_override_patch(
    suggestions: List[Dict[str, Any]],
    min_confidence: float = 0.9,
    max_items: int = 200,
    include_tables: Optional[List[str]] = None,
    exclude_roles: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    include_set = {str(t).strip().lower() for t in (include_tables or []) if str(t).strip()}
    exclude_set = {str(r).strip().lower() for r in (exclude_roles or []) if str(r).strip()}

    patch: Dict[str, Dict[str, Any]] = {}
    sorted_rows = sorted(suggestions, key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
    for row in sorted_rows:
        if len(patch) >= int(max_items):
            break

        confidence = float(row.get("confidence", 0.0) or 0.0)
        if confidence < float(min_confidence):
            continue

        table = str(row.get("table", "")).strip()
        column = str(row.get("column", "")).strip()
        role = str(row.get("suggested_role", "attribute")).strip().lower()
        if not table or not column:
            continue
        if include_set and table.lower() not in include_set:
            continue
        if role in exclude_set:
            continue

        dotted = f"{_normalize_token(table)}.{_normalize_token(column)}"
        patch[dotted] = {
            "role": role,
            "entity": str(row.get("entity", "unknown")),
            "canonical_name": str(row.get("canonical_name", _normalize_token(column))),
            "business_term": str(row.get("business_term", column)),
            "confidence": round(confidence, 3),
            "source": "auto-suggestion",
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }

    return patch


def apply_override_patch(
    config: Dict[str, Any],
    patch: Dict[str, Dict[str, Any]],
    overwrite_existing: bool = False,
) -> Dict[str, Any]:
    updated = json.loads(json.dumps(config))
    overrides = updated.setdefault("column_overrides", {})
    if not isinstance(overrides, dict):
        overrides = {}
        updated["column_overrides"] = overrides

    applied = 0
    skipped_existing = 0
    for dotted, rule in patch.items():
        if dotted in overrides and not overwrite_existing:
            skipped_existing += 1
            continue
        overrides[dotted] = rule
        applied += 1

    return {
        "config": updated,
        "applied": applied,
        "skipped_existing": skipped_existing,
        "proposed": len(patch),
    }


def summarize_semantic_layer(semantic_layer: Dict[str, Any]) -> Dict[str, Any]:
    suggestions_blob = semantic_layer.get("mapping_suggestions", {}) if isinstance(semantic_layer, dict) else {}
    suggestions = suggestions_blob.get("suggestions", []) if isinstance(suggestions_blob, dict) else []
    role_counts: Dict[str, int] = {}
    for row in suggestions if isinstance(suggestions, list) else []:
        role = str(row.get("suggested_role", "attribute")).strip().lower()
        role_counts[role] = int(role_counts.get(role, 0) + 1)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_version": str(semantic_layer.get("config_version", "1.0.0")),
        "avg_role_confidence": float(semantic_layer.get("avg_role_confidence", 0.0) or 0.0),
        "constraint_violations": len(semantic_layer.get("constraints", []) or []),
        "ambiguities": len(semantic_layer.get("ambiguities", []) or []),
        "total_suggestions": int(suggestions_blob.get("total_columns", len(suggestions) if isinstance(suggestions, list) else 0)),
        "role_distribution": role_counts,
        "uplift_report": semantic_layer.get("uplift_report", {}),
    }


def load_semantic_history(limit: int = 100) -> List[Dict[str, Any]]:
    if not SEMANTIC_HISTORY_FILE.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in SEMANTIC_HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    rows.append(parsed)
            except Exception:
                continue
    except Exception:
        return []
    return rows[-max(1, int(limit)):]


def append_semantic_history(summary: Dict[str, Any], source: str = "analysis") -> None:
    try:
        SEMANTIC_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        row = dict(summary)
        row["source"] = source
        with SEMANTIC_HISTORY_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        return


def compute_semantic_drift(current_summary: Dict[str, Any], previous_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not previous_summary:
        return {
            "has_previous": False,
            "message": "No previous semantic run found.",
            "delta_avg_role_confidence": None,
            "delta_constraint_violations": None,
            "delta_ambiguities": None,
            "role_distribution_delta": {},
        }

    curr_conf = float(current_summary.get("avg_role_confidence", 0.0) or 0.0)
    prev_conf = float(previous_summary.get("avg_role_confidence", 0.0) or 0.0)
    curr_v = int(current_summary.get("constraint_violations", 0) or 0)
    prev_v = int(previous_summary.get("constraint_violations", 0) or 0)
    curr_a = int(current_summary.get("ambiguities", 0) or 0)
    prev_a = int(previous_summary.get("ambiguities", 0) or 0)

    curr_roles = current_summary.get("role_distribution", {}) if isinstance(current_summary.get("role_distribution"), dict) else {}
    prev_roles = previous_summary.get("role_distribution", {}) if isinstance(previous_summary.get("role_distribution"), dict) else {}
    all_roles = sorted(set(curr_roles.keys()) | set(prev_roles.keys()))
    role_delta = {role: int(curr_roles.get(role, 0)) - int(prev_roles.get(role, 0)) for role in all_roles}

    return {
        "has_previous": True,
        "previous_timestamp": previous_summary.get("timestamp"),
        "delta_avg_role_confidence": round(curr_conf - prev_conf, 4),
        "delta_constraint_violations": int(curr_v - prev_v),
        "delta_ambiguities": int(curr_a - prev_a),
        "role_distribution_delta": role_delta,
    }
