from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .schema import classify_values, hashable_series, semantic_label


def _compute_temporal_adjustment(series: pd.Series, expected_gap_days: Optional[float] = None) -> Dict:
    parsed = pd.to_datetime(series, errors="coerce").dropna().sort_values()
    if len(parsed) < 3:
        return {
            "signal": False,
            "expected_gap_days": None,
            "lag_days": None,
            "lag_ratio": None,
            "regularity_score": None,
            "adjustment_points": 0.0,
        }

    gap_days = parsed.diff().dropna().dt.total_seconds() / 86400.0
    positive_gaps = gap_days[gap_days > 0]
    if positive_gaps.empty:
        return {
            "signal": False,
            "expected_gap_days": None,
            "lag_days": None,
            "lag_ratio": None,
            "regularity_score": None,
            "adjustment_points": 0.0,
        }

    inferred_gap_days = float(np.median(positive_gaps))
    target_gap_days = float(expected_gap_days) if expected_gap_days and expected_gap_days > 0 else inferred_gap_days
    mean_gap_days = float(np.mean(positive_gaps))
    std_gap_days = float(np.std(positive_gaps))
    variation = std_gap_days / max(mean_gap_days, 1e-6)

    # 1.0 means very stable cadence; 0.0 means highly irregular cadence.
    regularity_score = max(0.0, 1.0 - min(variation, 2.0) / 2.0)

    observed_gap_days = float((parsed.iloc[-1] - parsed.iloc[-2]).total_seconds() / 86400.0)
    lag_days = max(0.0, observed_gap_days)
    lag_ratio = lag_days / max(target_gap_days, 1e-6)

    cadence_bonus = (regularity_score - 0.5) * 10.0
    stoppage_penalty = min(8.0, max(0.0, lag_ratio - 1.75) * 1.5)
    adjustment_points = max(-10.0, min(10.0, cadence_bonus - stoppage_penalty))

    return {
        "signal": True,
        "expected_gap_days": target_gap_days,
        "inferred_gap_days": inferred_gap_days,
        "lag_days": lag_days,
        "lag_ratio": lag_ratio,
        "regularity_score": regularity_score,
        "adjustment_points": adjustment_points,
    }


def profile_table(
    table_name: str,
    df: pd.DataFrame,
    total_rows: int,
    pk_candidates: List[str],
    expected_cadence_days: Optional[float] = None,
) -> Dict:
    col_profiles: List[Dict] = []
    issues: List[str] = []
    completeness_values: List[float] = []
    consistency_values: List[float] = []
    temporal_adjustments: List[float] = []
    temporal_signal_columns = 0

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

        temporal_expected_gap_days = None
        temporal_lag_days = None
        temporal_lag_ratio = None
        temporal_regularity_score = None
        temporal_adjustment_points = None
        temporal_inferred_gap_days = None
        if semantic == "time dimension":
            temporal = _compute_temporal_adjustment(series, expected_gap_days=expected_cadence_days)
            if temporal["signal"]:
                temporal_signal_columns += 1
                temporal_expected_gap_days = float(temporal["expected_gap_days"])
                temporal_inferred_gap_days = float(temporal.get("inferred_gap_days", temporal_expected_gap_days))
                temporal_lag_days = float(temporal["lag_days"])
                temporal_lag_ratio = float(temporal["lag_ratio"])
                temporal_regularity_score = float(temporal["regularity_score"])
                temporal_adjustment_points = float(temporal["adjustment_points"])
                temporal_adjustments.append(temporal_adjustment_points)

                if temporal_lag_ratio >= 4.0:
                    issues.append(
                        f"{table_name}.{col} appears to have a possible data stoppage "
                        f"(latest observed interval is {temporal_lag_ratio:.1f}x longer than expected cadence)."
                    )
                if temporal_regularity_score < 0.35:
                    issues.append(
                        f"{table_name}.{col} has irregular update timing "
                        f"(regularity score {temporal_regularity_score:.2f})."
                    )

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
                "temporal_expected_gap_days": (
                    round(temporal_expected_gap_days, 2) if temporal_expected_gap_days is not None else None
                ),
                "temporal_inferred_gap_days": (
                    round(temporal_inferred_gap_days, 2) if temporal_inferred_gap_days is not None else None
                ),
                "temporal_lag_days": round(temporal_lag_days, 2) if temporal_lag_days is not None else None,
                "temporal_lag_ratio": round(temporal_lag_ratio, 2) if temporal_lag_ratio is not None else None,
                "temporal_regularity_score": (
                    round(temporal_regularity_score, 3) if temporal_regularity_score is not None else None
                ),
                "temporal_adjustment_points": (
                    round(temporal_adjustment_points, 2) if temporal_adjustment_points is not None else None
                ),
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
    base_quality_score = round((0.50 * completeness_score + 0.50 * consistency_score) * 100, 2)
    temporal_bonus_points = round(float(np.mean(temporal_adjustments)) if temporal_adjustments else 0.0, 2)
    quality_score = round(min(100.0, max(0.0, base_quality_score + temporal_bonus_points)), 2)

    return {
        "table": table_name,
        "sample_rows": int(len(df)),
        "estimated_total_rows": int(total_rows),
        "column_count": int(len(df.columns)),
        "pk_candidates": pk_candidates,
        "duplicate_pk_records": duplicate_pk_issues,
        "quality_score": quality_score,
        "base_quality_score": base_quality_score,
        "completeness_score": round(completeness_score * 100, 2),
        "consistency_score": round(consistency_score * 100, 2),
        "temporal_bonus_points": temporal_bonus_points,
        "temporal_signal_columns": temporal_signal_columns,
        "temporal_expected_cadence_days": round(expected_cadence_days, 4) if expected_cadence_days else None,
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
