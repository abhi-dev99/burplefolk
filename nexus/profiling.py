from datetime import datetime, timezone
from typing import Dict, List

import numpy as np
import pandas as pd

from .schema import classify_values, hashable_series, semantic_label


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
        safe_series = hashable_series(series)
        non_null = int(series.notna().sum())
        null_count = int(series.isna().sum())
        null_ratio = (null_count / max(1, len(df))) * 100
        unique_ratio = (safe_series.nunique(dropna=True) / max(1, non_null)) * 100 if non_null else 0
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
        safe_pk = hashable_series(df[pk])
        dupes = int(safe_pk.duplicated().sum())
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
