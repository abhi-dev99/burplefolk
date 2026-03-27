import json
import re
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned.lower() or "table"


def semantic_label(column_name: str) -> str:
    col = column_name.lower()
    if col.endswith("_id") or col == "id":
        return "identifier"
    if any(tok in col for tok in ["date", "time", "timestamp", "created", "updated"]):
        return "time dimension"
    if any(tok in col for tok in ["name", "title", "desc", "comment", "review", "text"]):
        return "descriptive text"
    if any(tok in col for tok in ["amount", "price", "cost", "revenue", "total", "value"]):
        return "financial metric"
    if any(tok in col for tok in ["status", "state", "type", "category", "segment"]):
        return "categorical attribute"
    if any(tok in col for tok in ["lat", "lng", "longitude", "latitude", "geo"]):
        return "geospatial attribute"
    return "general attribute"


def make_hashable(value):
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, set):
        return json.dumps(sorted(list(value)), default=str)
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), default=str)
    try:
        hash(value)
        return value
    except TypeError:
        return str(value)


def hashable_series(series: pd.Series) -> pd.Series:
    return series.map(make_hashable)


def normalize_key_value(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""

    if isinstance(value, (np.integer, int)):
        return str(int(value))

    if isinstance(value, (np.floating, float)):
        if np.isfinite(value) and float(value).is_integer():
            return str(int(value))
        return format(float(value), "g")

    text = str(value).strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered in {"null", "none", "nan", "na"}:
        return ""

    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".", 1)[0]

    return text


def key_value_set(series: pd.Series, limit: int = 15000) -> set:
    values = set()
    non_null = series.dropna()
    if non_null.empty:
        return values

    if len(non_null) > limit:
        # Spread picks across the full column to avoid head-only bias on large datasets.
        idx = np.linspace(0, len(non_null) - 1, num=limit, dtype=int)
        picked = non_null.iloc[idx]
    else:
        picked = non_null

    for raw in picked.tolist():
        normalized = normalize_key_value(raw)
        if normalized:
            values.add(normalized)
    return values


def infer_primary_keys(df: pd.DataFrame) -> List[str]:
    id_like = [c for c in df.columns if c.lower() == "id" or c.lower().endswith("_id")]
    id_keys: List[str] = []

    for col in id_like:
        series = df[col]
        if series.isna().any():
            continue
        safe_series = hashable_series(series)
        if safe_series.nunique(dropna=True) == len(safe_series):
            id_keys.append(col)

    if id_keys:
        return id_keys[:3]

    # Detect composite PKs in bridge-like tables when no single id-like key is unique.
    if len(id_like) >= 2:
        for i in range(len(id_like)):
            for j in range(i + 1, len(id_like)):
                pair = [id_like[i], id_like[j]]
                candidate = df[pair]
                if candidate.isna().any().any():
                    continue

                normalized = candidate.apply(lambda row: "|".join(normalize_key_value(v) for v in row), axis=1)
                if normalized.nunique(dropna=True) == len(candidate):
                    return pair

    keys: List[str] = []
    for col in df.columns:
        series = df[col]
        if series.isna().any():
            continue
        safe_series = hashable_series(series)
        if safe_series.nunique(dropna=True) == len(safe_series):
            keys.append(col)

    if not keys and "id" in df.columns:
        keys.append("id")

    return keys[:3]


def singularize_token(token: str) -> str:
    value = token.lower().strip()
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("s") and len(value) > 1 and not value.endswith("ss"):
        return value[:-1]
    return value


def strip_link_suffix(column_name: str) -> str:
    lower = column_name.lower()
    for suffix in ["_id", "_code", "_key", "_prefix"]:
        if lower.endswith(suffix):
            return lower[: -len(suffix)]
    return lower


def table_entity_core(table_name: str) -> str:
    parts = [p for p in table_name.lower().split("_") if p]
    noise_tokens = {"dataset", "table", "data"}
    if not parts:
        return table_name.lower()

    trimmed = [p for p in parts if p not in noise_tokens]
    if not trimmed:
        trimmed = parts

    # Common pattern: vendor prefix + business tokens + optional suffix (e.g., olist_order_items_dataset).
    if len(trimmed) >= 2 and trimmed[0] in {"olist", "dim", "fact", "stg"}:
        core_parts = [p for p in trimmed[1:] if p not in {"dataset", "table", "data"}]
        if core_parts:
            return "_".join(core_parts)
        return trimmed[1]

    return trimmed[-1]


def build_table_alias_maps(table_names: List[str]) -> Tuple[Dict[str, set], Dict[str, set]]:
    alias_to_tables: Dict[str, set] = {}
    table_to_aliases: Dict[str, set] = {}
    noise_tokens = {"dataset", "table", "data", "dim", "fact"}

    for table in table_names:
        base = table.lower()
        parts = base.split("_")
        variants = {
            base,
            singularize_token(base),
            base.replace("_", ""),
            singularize_token(base.replace("_", "")),
        }

        if len(parts) > 1:
            variants.add(parts[0])
            variants.add(singularize_token(parts[0]))
            variants.add(parts[-1])
            variants.add(singularize_token(parts[-1]))
            variants.add("_".join(parts[:-1]))
            variants.add(singularize_token("_".join(parts[:-1])))

            # Add middle/component tokens (e.g., olist_customers_dataset -> customers).
            for token in parts:
                token = token.strip()
                if not token or token in noise_tokens:
                    continue
                variants.add(token)
                variants.add(singularize_token(token))

        variants = {v for v in variants if v}
        table_to_aliases[table] = variants
        for alias in variants:
            alias_to_tables.setdefault(alias, set()).add(table)

    return alias_to_tables, table_to_aliases


def infer_foreign_keys(tables: Dict[str, pd.DataFrame], pk_map: Dict[str, List[str]]) -> List[Dict]:
    relationships: List[Dict] = []
    alias_to_tables, table_to_aliases = build_table_alias_maps(list(tables.keys()))

    pk_value_cache: Dict[Tuple[str, str], set] = {}
    for parent_table, pk_cols in pk_map.items():
        parent_df = tables[parent_table]
        for pk in pk_cols:
            values = key_value_set(parent_df[pk], limit=15000)
            pk_value_cache[(parent_table, pk)] = values

    for child_table, child_df in tables.items():
        child_pk_cols = set(pk_map.get(child_table, []))
        entity_id_col = f"{singularize_token(table_entity_core(child_table))}_id"

        for child_col in child_df.columns:
            child_lower = child_col.lower()
            is_link_like = (
                child_lower.endswith("_id")
                or child_lower.endswith("_code")
                or child_lower.endswith("_key")
                or child_lower.endswith("_prefix")
            )
            if not is_link_like:
                continue

            # Skip the canonical entity identifier column (e.g., customers.customer_id).
            if child_lower == entity_id_col:
                continue

            # Keep composite-key bridge columns (like stocks.store_id), but skip single-PK identity columns.
            if child_col in child_pk_cols and len(child_pk_cols) <= 1:
                continue

            child_token = strip_link_suffix(child_lower)
            child_values = key_value_set(child_df[child_col], limit=15000)
            if not child_values:
                continue

            candidate_tables = set()

            for alias in {child_token, singularize_token(child_token)}:
                matched = alias_to_tables.get(alias, set())
                if matched:
                    candidate_tables.update(matched)

            # If a PK has the exact same column name, include that table as a candidate.
            for (parent_table, parent_col), _ in pk_value_cache.items():
                if parent_col.lower() == child_lower:
                    candidate_tables.add(parent_table)

            # Never infer self-table links in ER mode.
            if child_table in candidate_tables:
                candidate_tables.discard(child_table)

            if not candidate_tables:
                continue

            best = None
            best_score = 0.0
            for parent_table in candidate_tables:
                for parent_col in pk_map.get(parent_table, []):
                    parent_series = hashable_series(tables[parent_table][parent_col].dropna())
                    if parent_series.empty:
                        continue
                    if parent_series.nunique(dropna=True) != len(parent_series):
                        continue

                    parent_values = pk_value_cache.get((parent_table, parent_col), set())
                    if not parent_values:
                        continue

                    overlap_ratio = len(child_values & parent_values) / max(1, len(child_values))

                    name_score = 0.0
                    table_match = child_token in table_to_aliases.get(parent_table, set())
                    if table_match:
                        name_score = max(name_score, 0.2)
                    if parent_col.lower() == child_lower:
                        # Exact column-name matches are only trusted strongly when table semantics also align.
                        name_score = max(name_score, 0.95 if table_match else 0.65)
                    if parent_col.lower() == "id" and table_match:
                        name_score = max(name_score, 0.8)
                    if singularize_token(table_entity_core(parent_table)) == singularize_token(child_token):
                        name_score = max(name_score, 0.98)

                    # Allow lower overlap for exact-name links on very large/high-cardinality datasets.
                    min_overlap = 0.08 if (parent_col.lower() == child_lower and table_match) else 0.25
                    if name_score < 0.75 or overlap_ratio < min_overlap:
                        continue

                    score = (0.70 * name_score) + (0.30 * overlap_ratio)
                    if score > best_score:
                        best_score = score
                        best = (parent_table, parent_col)

            if best:
                relationships.append(
                    {
                        "child_table": child_table,
                        "child_column": child_col,
                        "parent_table": best[0],
                        "parent_column": best[1],
                        "relation_type": "many-to-one",
                        "confidence": round(min(1.0, best_score), 3),
                    }
                )
    return relationships


def classify_values(series: pd.Series, sample_size: int = 3000) -> Dict[str, float]:
    sample = series.dropna().astype(str).head(sample_size)
    if sample.empty:
        return {"unknown": 1.0}

    counts = {"numeric": 0, "datetime": 0, "boolean": 0, "text": 0}
    for value in sample:
        lower = value.strip().lower()
        if lower in {"true", "false", "yes", "no", "0", "1"}:
            counts["boolean"] += 1
            continue

        try:
            float(value.replace(",", ""))
            counts["numeric"] += 1
            continue
        except ValueError:
            pass

        dt = pd.to_datetime(pd.Series([value]), errors="coerce")
        if not dt.isna().iloc[0]:
            counts["datetime"] += 1
        else:
            counts["text"] += 1

    total = sum(counts.values())
    return {k: round(v / total, 4) for k, v in counts.items() if total > 0}
