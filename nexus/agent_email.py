from __future__ import annotations

import imaplib
import json
import re
import smtplib
import threading
from calendar import month_name
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from typing import Any, Deque, Dict, List, Optional, Tuple

import pandas as pd


_EVENT_LOG: Deque[Dict] = deque(maxlen=200)
_EVENT_LOCK = threading.Lock()


def _log_event(level: str, message: str, metadata: Optional[Dict] = None) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "metadata": metadata or {},
    }
    with _EVENT_LOCK:
        _EVENT_LOG.appendleft(event)


def get_event_log(limit: int = 50) -> List[Dict]:
    with _EVENT_LOCK:
        return list(_EVENT_LOG)[:limit]


def firebase_email_password_login(
    firebase_api_key: str,
    firebase_auth_domain: str,
    firebase_project_id: str,
    firebase_storage_bucket: str,
    email: str,
    password: str,
) -> Tuple[bool, str, Optional[Dict]]:
    import requests
    
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        user_data = response.json()
        return True, "Firebase authentication succeeded.", user_data
    except requests.exceptions.RequestException as exc:
        error_msg = str(exc)
        try:
            if hasattr(exc, 'response') and exc.response is not None:
                error_detail = exc.response.json()
                if 'error' in error_detail:
                    error_msg = error_detail['error'].get('message', error_msg)
        except Exception:
            pass
        return False, f"Firebase authentication failed: {error_msg}", None
    except Exception as exc:
        return False, f"Firebase authentication failed: {exc}", None


def _extract_plain_text(msg) -> str:
    if msg.is_multipart():
        parts: List[str] = []
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    parts.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    parts.append(payload.decode(errors="ignore"))
        return "\n".join(x for x in parts if x).strip()

    try:
        return str(msg.get_content()).strip()
    except Exception:
        payload = msg.get_payload(decode=True) or b""
        return payload.decode(errors="ignore").strip()


def _first_question_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if "?" in ln:
            return ln
    return lines[0] if lines else ""


def _collect_reply_all_recipients(msg, agent_email: str) -> Tuple[List[str], List[str]]:
    addresses = getaddresses([msg.get("From", ""), msg.get("To", ""), msg.get("Cc", "")])
    dedup: List[str] = []
    seen = set()
    for _, addr in addresses:
        value = (addr or "").strip().lower()
        if not value or value == agent_email.lower() or value in seen:
            continue
        seen.add(value)
        dedup.append(value)

    to_email = parseaddr(msg.get("From", ""))[1].strip().lower()
    to_recipients = [to_email] if to_email and to_email != agent_email.lower() else []
    cc_recipients = [x for x in dedup if x not in to_recipients]
    return to_recipients, cc_recipients


def _best_table_by_keywords(tables: Dict[str, pd.DataFrame], keywords: List[str]) -> Optional[Tuple[str, pd.DataFrame]]:
    if not tables:
        return None

    def score_item(item: Tuple[str, pd.DataFrame]) -> int:
        table_name, frame = item
        score = 0
        lower_name = table_name.lower()
        cols = [str(c).lower() for c in frame.columns]
        for kw in keywords:
            if kw in lower_name:
                score += 5
            score += sum(1 for c in cols if kw in c)
        return score

    ranked = sorted(tables.items(), key=score_item, reverse=True)
    top_name, top_df = ranked[0]
    if score_item((top_name, top_df)) <= 0:
        return None
    return top_name, top_df


def _pick_date_column(df: pd.DataFrame) -> Optional[str]:
    candidates = [c for c in df.columns if any(k in str(c).lower() for k in ["date", "time", "created", "updated", "timestamp"])]
    return str(candidates[0]) if candidates else None


def _pick_numeric_column(df: pd.DataFrame, preferred_terms: List[str]) -> Optional[str]:
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return None
    for term in preferred_terms:
        for col in numeric_cols:
            if term in str(col).lower():
                return str(col)
    return str(numeric_cols[0])


def answer_question_from_tables(question: str, tables: Dict[str, pd.DataFrame]) -> str:
    query = (question or "").strip().lower()
    if not query:
        return "I could not detect a query in the received email body."

    employee_words = ["employee", "employees", "staff", "associate", "worker"]
    sales_words = ["sales", "revenue", "amount", "gmv", "order_total", "total", "value", "aov", "average order"]
    top_products_query = (
        any(token in query for token in ["top", "highest", "best", "most"]) and
        any(token in query for token in ["product", "item"]) and
        any(token in query for token in ["revenue", "sales", "amount", "gmv"])
    )

    if any(w in query for w in employee_words) and any(w in query for w in ["how many", "number", "count", "total"]):
        match = _best_table_by_keywords(tables, ["employee", "staff", "hr", "team"])
        if not match:
            return "I could not locate an employee table in the current dataset snapshot."
        table_name, frame = match
        if frame.empty:
            return f"The `{table_name}` table is empty in the current dataset snapshot."

        id_candidates = [
            c for c in frame.columns if any(k in str(c).lower() for k in ["employee_id", "emp_id", "staff_id", "id"])
        ]
        if id_candidates:
            count_val = int(frame[id_candidates[0]].nunique(dropna=True))
        else:
            count_val = int(len(frame.index))

        return f"There are currently {count_val} employees based on the available `{table_name}` dataset snapshot."

    if any(w in query for w in sales_words) and not top_products_query:
        match = _best_table_by_keywords(tables, ["sale", "order", "invoice", "transaction", "revenue"])
        if not match:
            return "I could not locate a sales-related table in the current dataset snapshot."

        table_name, frame = match
        if frame.empty:
            return f"The `{table_name}` table is empty in the current dataset snapshot."

        working = frame.copy()
        if "last month" in query:
            date_col = _pick_date_column(working)
            if date_col:
                parsed = pd.to_datetime(working[date_col], errors="coerce")
                now_utc = datetime.now(timezone.utc)
                first_day_this_month = datetime(now_utc.year, now_utc.month, 1, tzinfo=timezone.utc)
                if first_day_this_month.month == 1:
                    first_day_last_month = datetime(first_day_this_month.year - 1, 12, 1, tzinfo=timezone.utc)
                else:
                    first_day_last_month = datetime(first_day_this_month.year, first_day_this_month.month - 1, 1, tzinfo=timezone.utc)
                mask = (parsed >= first_day_last_month) & (parsed < first_day_this_month)
                working = working.loc[mask.fillna(False)]

        lower_cols = {str(c).lower(): str(c) for c in working.columns}
        if "list_price" in lower_cols and "quantity" in lower_cols:
            amount = pd.to_numeric(working[lower_cols["list_price"]], errors="coerce").fillna(0) * pd.to_numeric(
                working[lower_cols["quantity"]], errors="coerce"
            ).fillna(0)
            total = float(amount.sum()) if len(amount) else 0.0
            return f"Sales for the requested period is {total:,.2f}."

        metric_col = _pick_numeric_column(frame, ["sales", "revenue", "amount", "total", "value", "price"])
        if not metric_col:
            return f"I could not find a numeric sales metric column in `{table_name}`."

        value = pd.to_numeric(working[metric_col], errors="coerce").fillna(0)

        if any(x in query for x in ["average", "avg", "mean"]):
            result = float(value.mean()) if len(value) else 0.0
            return f"Average `{metric_col}` is {result:,.2f} from `{table_name}` based on the current dataset snapshot."

        if any(x in query for x in ["count", "how many"]):
            return f"There are {int(value.count())} matching records in `{table_name}` based on the current dataset snapshot."

        total = float(value.sum()) if len(value) else 0.0
        return f"Sales for the requested period is {total:,.2f}."

    for table_name, frame in tables.items():
        if table_name.lower() in query and any(x in query for x in ["count", "how many", "number", "total records"]):
            return f"The `{table_name}` table currently has {int(len(frame.index))} rows in the analyzed dataset snapshot."

    return (
        "I could not confidently map this question to a supported metric intent. "
        "Try queries like 'how many employees are there today?' or 'what are the sales for the last month?'."
    )


def _answer_average_order_value_per_customer(question: str, tables: Dict[str, pd.DataFrame]) -> Optional[str]:
    q = (question or "").lower()
    if not (
        any(token in q for token in ["average", "avg", "mean", "aov"]) and
        any(token in q for token in ["order", "sales", "revenue", "value"]) and
        "customer" in q
    ):
        return None

    best_table: Optional[Tuple[str, pd.DataFrame, str, Optional[str], Optional[str]]] = None
    best_score = -1

    for table_name, frame in tables.items():
        if frame.empty:
            continue

        cols = [str(c) for c in frame.columns]
        customer_col = _pick_best_column(cols, ["customer_id", "client_id", "account_id", "customer", "client"])
        if not customer_col:
            continue

        order_col = _pick_best_column(cols, ["order_id", "invoice_id", "transaction_id", "sale_id", "order"])
        amount_col = _pick_numeric_column(frame, ["order_total", "revenue", "amount", "sales", "total", "value", "price"])
        qty_col = _pick_best_column(cols, ["quantity", "qty", "order_quantity"])
        unit_price_col = _pick_best_column(cols, ["unit_price", "list_price", "price", "amount"])

        has_amount = amount_col is not None
        has_price_qty = qty_col is not None and unit_price_col is not None
        if not has_amount and not has_price_qty:
            continue

        score = 0
        tname = str(table_name).lower()
        if any(tok in tname for tok in ["order", "sale", "invoice", "transaction", "detail", "line"]):
            score += 5
        if has_amount:
            score += 3
        if has_price_qty:
            score += 2
        if order_col:
            score += 2

        if score > best_score:
            best_score = score
            best_table = (table_name, frame, customer_col, order_col, amount_col)

    if not best_table:
        return None

    table_name, frame, customer_col, order_col, amount_col = best_table
    work = frame.copy()

    if amount_col is not None:
        work["__amount"] = pd.to_numeric(work[amount_col], errors="coerce").fillna(0)
    else:
        price_col = _pick_best_column([str(c) for c in work.columns], ["unit_price", "list_price", "price", "amount"])
        qty_col = _pick_best_column([str(c) for c in work.columns], ["quantity", "qty", "order_quantity"])
        if not price_col or not qty_col:
            return None
        work["__amount"] = pd.to_numeric(work[price_col], errors="coerce").fillna(0) * pd.to_numeric(work[qty_col], errors="coerce").fillna(0)

    # Compute order totals first where order identifier exists, then per-customer AOV.
    if order_col and order_col in work.columns:
        per_order = (
            work.groupby([customer_col, order_col], as_index=False)["__amount"]
            .sum()
            .rename(columns={"__amount": "order_value"})
        )
        per_customer = (
            per_order.groupby(customer_col, as_index=False)["order_value"]
            .mean()
            .rename(columns={"order_value": "aov"})
            .sort_values("aov", ascending=False)
        )
        overall_aov = float(per_order["order_value"].mean()) if len(per_order) else 0.0
        customer_count = int(per_customer[customer_col].nunique()) if len(per_customer) else 0
    else:
        per_customer = (
            work.groupby(customer_col, as_index=False)["__amount"]
            .mean()
            .rename(columns={"__amount": "aov"})
            .sort_values("aov", ascending=False)
        )
        overall_aov = float(work["__amount"].mean()) if len(work) else 0.0
        customer_count = int(per_customer[customer_col].nunique()) if len(per_customer) else 0

    top_n = min(5, len(per_customer))
    top_rows = per_customer.head(top_n)
    top_lines = [
        f"- Customer {row[customer_col]}: {_format_number_compact(float(row['aov']))}"
        for _, row in top_rows.iterrows()
    ]

    return (
        f"Average order value per customer is {_format_number_compact(overall_aov)}.\n"
        f"Computed from `{table_name}` using customer key `{customer_col}`"
        + (f" and order key `{order_col}`." if order_col else ".")
        + f"\nCustomers analyzed: {customer_count}.\nTop {top_n} customers by AOV:\n"
        + "\n".join(top_lines)
    )


def _extract_numeric_id(question: str) -> Optional[int]:
    q = (question or "").lower()
    patterns = [
        r"\b(?:customer|client|user|account|employee)\s*_?id\s*(?:=|is|:)?\s*(\d+)\b",
        r"\b(?:customer|client|user|account|employee)\s+#?(\d+)\b",
        r"\bid\s*(?:=|is|:)?\s*(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
    return None


def _requested_attributes(question: str) -> List[str]:
    q = (question or "").lower()
    attrs: List[str] = []
    keyword_map = {
        "name": ["name", "full name", "customer name", "first name", "last name"],
        "email": ["email", "mail"],
        "phone": ["phone", "mobile", "contact number", "telephone"],
        "address": ["address", "location"],
        "city": ["city", "town"],
        "state": ["state", "province"],
        "country": ["country"],
    }
    for attr, terms in keyword_map.items():
        if any(term in q for term in terms):
            attrs.append(attr)
    return attrs


def _pick_best_column(columns: List[str], hints: List[str]) -> Optional[str]:
    lowered = {str(col).lower(): str(col) for col in columns}
    for hint in hints:
        for key, original in lowered.items():
            if key == hint or key.endswith(f"_{hint}") or hint in key:
                return original
    return None


def _best_table_for_entity_lookup(question: str, tables: Dict[str, pd.DataFrame]) -> Optional[Tuple[str, pd.DataFrame, str]]:
    q = (question or "").lower()
    best: Optional[Tuple[str, pd.DataFrame, str]] = None
    best_score = -1

    for table_name, df in tables.items():
        cols = [str(c) for c in df.columns]
        cols_lower = [c.lower() for c in cols]
        id_candidates = [
            c
            for c in cols
            if str(c).lower() == "id" or str(c).lower().endswith("_id") or "customer_id" in str(c).lower()
        ]
        if not id_candidates:
            continue

        score = 0
        tname = str(table_name).lower()
        if any(token in q for token in ["customer", "client", "user", "account", "employee"]):
            if any(token in tname for token in ["customer", "client", "user", "account", "employee"]):
                score += 6

        if any("customer_id" in c.lower() for c in id_candidates):
            score += 5

        if any(x in cols_lower for x in ["email", "phone", "name", "full_name", "customer_name"]):
            score += 3

        if len(df.index) > 0:
            score += 1

        if score > best_score:
            best_score = score
            best = (table_name, df, id_candidates[0])

    return best


def _answer_entity_lookup(question: str, tables: Dict[str, pd.DataFrame]) -> Optional[str]:
    q = (question or "").lower()
    if "id" not in q and not any(token in q for token in ["customer", "client", "user", "account", "employee"]):
        return None

    entity_id = _extract_numeric_id(question)
    if entity_id is None:
        return None

    table_pick = _best_table_for_entity_lookup(question, tables)
    if not table_pick:
        return None

    table_name, df, id_col = table_pick
    if df.empty:
        return f"The `{table_name}` table is empty in the current dataset snapshot."

    id_series = pd.to_numeric(df[id_col], errors="coerce")
    matches = df.loc[id_series == float(entity_id)]
    if matches.empty:
        return f"I could not find a record with `{id_col} = {entity_id}` in `{table_name}`."

    attrs = _requested_attributes(question)
    cols = [str(c) for c in df.columns]
    selected_cols: List[str] = []

    mapping = {
        "name": ["full_name", "customer_name", "name", "first_name", "last_name"],
        "email": ["email", "email_address", "mail"],
        "phone": ["phone", "phone_number", "mobile", "contact"],
        "address": ["address", "street", "addr"],
        "city": ["city"],
        "state": ["state", "province"],
        "country": ["country"],
    }
    for attr in attrs:
        picked = _pick_best_column(cols, mapping.get(attr, [attr]))
        if picked and picked not in selected_cols:
            selected_cols.append(picked)

    if id_col not in selected_cols:
        selected_cols.insert(0, id_col)

    if not attrs:
        # If no explicit attribute request, return a concise but informative row preview.
        selected_cols = [id_col] + [c for c in cols if c != id_col][:5]

    row = matches.iloc[0]
    details = []
    for col in selected_cols:
        if col not in matches.columns:
            continue
        value = row[col]
        if pd.isna(value):
            value = "null"
        details.append(f"{col}: {value}")

    details_txt = "\n".join(f"- {item}" for item in details) if details else "- No requested attributes were found in the matched record."
    return (
        f"I found a matching record in `{table_name}` for `{id_col} = {entity_id}`.\n"
        f"Requested details:\n{details_txt}"
    )


def _answer_highest_revenue_month(question: str, tables: Dict[str, pd.DataFrame]) -> Optional[str]:
    q = (question or "").lower()
    if not (
        any(token in q for token in ["highest", "max", "top"]) and
        any(token in q for token in ["revenue", "sales", "gmv", "amount"]) and
        "month" in q
    ):
        return None

    best_table = _best_table_by_keywords(tables, ["sale", "order", "invoice", "transaction", "revenue", "amount"])
    if not best_table:
        return None

    table_name, frame = best_table
    if frame.empty:
        return f"The `{table_name}` table is empty in the current dataset snapshot."

    date_col = _pick_date_column(frame)
    if not date_col:
        return f"I found `{table_name}`, but could not identify a date column to compute monthly revenue."

    amount_col = _pick_numeric_column(frame, ["revenue", "amount", "total", "sales", "value", "price"])
    if not amount_col:
        lower_cols = {str(c).lower(): str(c) for c in frame.columns}
        if "list_price" in lower_cols and "quantity" in lower_cols:
            amount_series = pd.to_numeric(frame[lower_cols["list_price"]], errors="coerce").fillna(0) * pd.to_numeric(
                frame[lower_cols["quantity"]], errors="coerce"
            ).fillna(0)
        else:
            return f"I found `{table_name}`, but no numeric revenue-like column was available."
    else:
        amount_series = pd.to_numeric(frame[amount_col], errors="coerce").fillna(0)

    parsed_dates = pd.to_datetime(frame[date_col], errors="coerce")
    valid_mask = parsed_dates.notna()
    if not valid_mask.any():
        return f"I found `{table_name}`, but all values in `{date_col}` were invalid for date parsing."

    monthly = (
        pd.DataFrame({"date": parsed_dates[valid_mask], "amount": amount_series[valid_mask]})
        .assign(month=lambda d: d["date"].dt.to_period("M"))
        .groupby("month", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )
    if monthly.empty:
        return "I could not compute monthly revenue from the available records."

    top = monthly.iloc[0]
    top_period = top["month"]
    top_value = float(top["amount"])
    month_num = int(str(top_period).split("-")[1]) if "-" in str(top_period) else 0
    month_label = f"{month_name[month_num]} {str(top_period).split('-')[0]}" if 1 <= month_num <= 12 else str(top_period)
    top3 = monthly.head(3)
    top3_txt = "\n".join(
        f"- {str(row.month)}: {_format_number_compact(float(row.amount))}"
        for row in top3.itertuples(index=False)
    )
    return (
        f"The highest revenue month is **{month_label}** with revenue of {_format_number_compact(top_value)}.\n"
        f"Computed from `{table_name}` using `{date_col}` and {'derived price*quantity' if amount_col is None else amount_col}.\n"
        f"Top months:\n{top3_txt}"
    )


def _extract_top_n(question: str, default: int = 5) -> int:
    q = (question or "").lower()
    match = re.search(r"\btop\s+(\d+)\b", q)
    if match:
        try:
            return max(1, min(25, int(match.group(1))))
        except Exception:
            return default
    return default


def _pick_product_dimension_table(tables: Dict[str, pd.DataFrame], product_key: str) -> Optional[Tuple[str, pd.DataFrame, str, Optional[str]]]:
    key_l = product_key.lower()
    best: Optional[Tuple[str, pd.DataFrame, str, Optional[str]]] = None
    best_score = -1

    for tname, df in tables.items():
        cols = [str(c) for c in df.columns]
        cols_lower = [c.lower() for c in cols]
        if len(df.index) == 0:
            continue

        join_col = None
        for col in cols:
            c = str(col).lower()
            if c == key_l or c.endswith("_id") and ("product" in c or "stockitem" in c):
                join_col = str(col)
                break
        if not join_col:
            continue

        name_col = _pick_best_column(cols, ["product_name", "stockitemname", "name", "description", "item_name"])
        score = 0
        tl = str(tname).lower()
        if any(tok in tl for tok in ["product", "item", "stock", "catalog"]):
            score += 6
        if name_col:
            score += 5
        if df[join_col].nunique(dropna=True) > 0:
            score += 2

        if score > best_score:
            best_score = score
            best = (tname, df, join_col, name_col)

    return best


def _answer_top_products_by_revenue(question: str, tables: Dict[str, pd.DataFrame]) -> Optional[str]:
    q = (question or "").lower()
    if not any(token in q for token in ["top", "highest", "best", "most"]):
        return None
    if "product" not in q and "item" not in q:
        return None
    if not any(token in q for token in ["revenue", "sales", "amount", "gmv"]):
        return None

    top_n = _extract_top_n(question, default=5)

    # Find likely sales line table containing product key and numeric monetary signal.
    best_table: Optional[Tuple[str, pd.DataFrame, str, Optional[str], Optional[str]]] = None
    best_score = -1
    for tname, df in tables.items():
        if df.empty:
            continue
        cols = [str(c) for c in df.columns]
        cols_lower = [c.lower() for c in cols]

        product_col = _pick_best_column(cols, ["product_id", "stockitemid", "item_id", "sku", "product"])
        if not product_col:
            continue

        amount_col = _pick_numeric_column(df, ["revenue", "amount", "line_total", "total", "sales", "price", "value"])
        quantity_col = _pick_best_column(cols, ["quantity", "qty", "order_quantity"])
        price_col = _pick_best_column(cols, ["list_price", "unit_price", "price", "amount"])

        has_direct_amount = amount_col is not None
        has_price_qty = quantity_col is not None and price_col is not None
        if not has_direct_amount and not has_price_qty:
            continue

        score = 0
        tl = str(tname).lower()
        if any(tok in tl for tok in ["order", "sale", "invoice", "transaction", "line", "detail"]):
            score += 5
        if has_direct_amount:
            score += 3
        if has_price_qty:
            score += 3
        if len(df.index) > 100:
            score += 1

        if score > best_score:
            best_score = score
            best_table = (tname, df, product_col, amount_col, quantity_col if price_col else None)

    if not best_table:
        return None

    table_name, frame, product_col, amount_col, quantity_col = best_table
    work = frame.copy()

    if amount_col is not None:
        revenue = pd.to_numeric(work[amount_col], errors="coerce").fillna(0)
    else:
        price_col = _pick_best_column(list(work.columns), ["list_price", "unit_price", "price", "amount"])
        if not price_col or not quantity_col:
            return None
        revenue = pd.to_numeric(work[price_col], errors="coerce").fillna(0) * pd.to_numeric(work[quantity_col], errors="coerce").fillna(0)

    grouped = (
        pd.DataFrame({"product_key": work[product_col], "revenue": revenue})
        .dropna(subset=["product_key"])
        .groupby("product_key", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .head(top_n)
    )
    if grouped.empty:
        return "I could not compute top products because no product-revenue rows were available."

    # Try to map product IDs to names from a likely product dimension table.
    dim_pick = _pick_product_dimension_table(tables, str(product_col))
    product_label_col: Optional[str] = None
    if dim_pick:
        _, dim_df, dim_key_col, dim_name_col = dim_pick
        if dim_name_col and dim_key_col:
            mapping_df = dim_df[[dim_key_col, dim_name_col]].dropna(subset=[dim_key_col]).drop_duplicates(subset=[dim_key_col])
            grouped = grouped.merge(mapping_df, how="left", left_on="product_key", right_on=dim_key_col)
            product_label_col = dim_name_col

    lines: List[str] = []
    for idx, (_, row) in enumerate(grouped.iterrows(), start=1):
        label = row.get(product_label_col) if product_label_col else row.get("product_key")
        if pd.isna(label):
            label = row.get("product_key")
        lines.append(f"{idx}. {label} - {_format_number_compact(float(row.get('revenue', 0.0)))}")

    revenue_source = amount_col if amount_col else "derived(unit_price * quantity)"
    return (
        f"Top {len(lines)} products by revenue:\n"
        + "\n".join(lines)
        + f"\n\nComputed from `{table_name}` using product key `{product_col}` and revenue source `{revenue_source}`."
    )


def _deterministic_agent_answer(question: str, tables: Dict[str, pd.DataFrame]) -> Optional[str]:
    for handler in (
        _answer_entity_lookup,
        _answer_top_products_by_revenue,
        _answer_highest_revenue_month,
        _answer_average_order_value_per_customer,
    ):
        try:
            result = handler(question, tables)
            if result:
                return result
        except Exception:
            continue
    return None


def _build_provider_chain(ai_provider: str, gemini_api_key: str) -> List[str]:
    preferred = "gemini" if (ai_provider or "").strip().lower() == "gemini" else "ollama"
    chain = [preferred]
    if preferred == "ollama" and gemini_api_key.strip():
        chain.append("gemini")
    elif preferred == "gemini":
        chain.append("ollama")
    return chain


def _extract_threshold(question: str, default: int = 5) -> int:
    q = (question or "").lower()
    patterns = [
        r"(?:more than|greater than|over|above)\s+(\d+)",
        r"(?:at least|minimum of|min)\s+(\d+)",
        r"(?:less than|below|under)\s+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return default
    return default


def _find_table(
    tables: Dict[str, pd.DataFrame],
    name_keywords: List[str],
    required_columns: Optional[List[str]] = None,
) -> Optional[Tuple[str, pd.DataFrame]]:
    required_columns = required_columns or []
    ranked: List[Tuple[int, str, pd.DataFrame]] = []
    for table_name, frame in tables.items():
        lower_name = str(table_name).lower()
        cols = [str(c).lower() for c in frame.columns]
        score = 0
        for kw in name_keywords:
            if kw in lower_name:
                score += 4
            score += sum(1 for c in cols if kw in c)
        if required_columns and not all(any(req in c for c in cols) for req in required_columns):
            continue
        if score > 0:
            ranked.append((score, table_name, frame))
    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    _, table_name, frame = ranked[0]
    return table_name, frame


def _rule_based_sql_planner(question: str, tables: Dict[str, pd.DataFrame]) -> str:
    q = (question or "").lower()

    # Pattern: customers with more than N orders
    if "customer" in q and "order" in q and any(tok in q for tok in ["more than", "greater than", "over", "at least"]):
        threshold = _extract_threshold(question, default=5)
        orders_pick = _find_table(tables, ["order", "orders"], required_columns=["order", "customer"])
        if orders_pick:
            orders_table, orders_df = orders_pick
            ocols = [str(c) for c in orders_df.columns]
            customer_col = _pick_best_column(ocols, ["customer_id", "customer", "client_id"])
            order_col = _pick_best_column(ocols, ["order_id", "order"])
            if customer_col and order_col:
                customers_pick = _find_table(tables, ["customer", "customers"], required_columns=["customer"])
                if customers_pick:
                    customers_table, customers_df = customers_pick
                    ccols = [str(c) for c in customers_df.columns]
                    customers_key = _pick_best_column(ccols, ["customer_id", "customer", "id"])
                    if customers_key:
                        name_col = _pick_best_column(ccols, ["first_name", "last_name", "name"])
                        email_col = _pick_best_column(ccols, ["email", "mail"])
                        select_parts = [f"o.{customer_col} AS customer_id", f"COUNT(DISTINCT o.{order_col}) AS order_count"]
                        if name_col:
                            select_parts.insert(1, f"c.{name_col} AS customer_name")
                        if email_col:
                            select_parts.append(f"c.{email_col} AS email")
                        select_clause = ",\n  ".join(select_parts)
                        return (
                            f"SELECT\n  {select_clause}\n"
                            f"FROM {orders_table} o\n"
                            f"LEFT JOIN {customers_table} c ON o.{customer_col} = c.{customers_key}\n"
                            f"GROUP BY o.{customer_col}"
                            + (f", c.{name_col}" if name_col else "")
                            + (f", c.{email_col}" if email_col else "")
                            + f"\nHAVING COUNT(DISTINCT o.{order_col}) > {int(threshold)}\n"
                              "ORDER BY order_count DESC\nLIMIT 50"
                        )
                return (
                    f"SELECT {customer_col} AS customer_id, COUNT(DISTINCT {order_col}) AS order_count\n"
                    f"FROM {orders_table}\n"
                    f"GROUP BY {customer_col}\n"
                    f"HAVING COUNT(DISTINCT {order_col}) > {int(threshold)}\n"
                    "ORDER BY order_count DESC\nLIMIT 50"
                )

    # Pattern: top N products by revenue
    if any(tok in q for tok in ["top", "highest", "best", "most"]) and "product" in q and any(tok in q for tok in ["revenue", "sales", "amount", "gmv"]):
        top_n = _extract_top_n(question, default=5)
        items_pick = _find_table(tables, ["order_items", "item", "line"], required_columns=["product", "quantity"])
        if items_pick:
            items_table, items_df = items_pick
            icols = [str(c) for c in items_df.columns]
            product_col = _pick_best_column(icols, ["product_id", "product", "item_id", "stockitemid"])
            qty_col = _pick_best_column(icols, ["quantity", "qty"])
            price_col = _pick_best_column(icols, ["list_price", "unit_price", "price", "amount"])
            discount_col = _pick_best_column(icols, ["discount"])
            if product_col and qty_col and price_col:
                products_pick = _find_table(tables, ["product", "products"], required_columns=["product"])
                revenue_expr = (
                    f"(oi.{qty_col} * oi.{price_col} * (1 - COALESCE(oi.{discount_col}, 0)))"
                    if discount_col
                    else f"(oi.{qty_col} * oi.{price_col})"
                )
                if products_pick:
                    products_table, products_df = products_pick
                    pcols = [str(c) for c in products_df.columns]
                    p_key = _pick_best_column(pcols, ["product_id", "product", "id"])
                    p_name = _pick_best_column(pcols, ["product_name", "name", "item_name"])
                    if p_key:
                        return (
                            "SELECT\n"
                            f"  oi.{product_col} AS product_id,\n"
                            + (f"  p.{p_name} AS product_name,\n" if p_name else "")
                            +
                            f"  SUM({revenue_expr}) AS revenue\n"
                            f"FROM {items_table} oi\n"
                            f"LEFT JOIN {products_table} p ON oi.{product_col} = p.{p_key}\n"
                            f"GROUP BY oi.{product_col}"
                            + (f", p.{p_name}" if p_name else "")
                            + "\nORDER BY revenue DESC\n"
                            + f"LIMIT {int(top_n)}"
                        )

    # Pattern: average order value per customer
    if any(tok in q for tok in ["average", "avg", "mean", "aov"]) and "order" in q and "customer" in q:
        orders_pick = _find_table(tables, ["order", "orders"], required_columns=["order", "customer"])
        items_pick = _find_table(tables, ["order_items", "item", "line"], required_columns=["order", "quantity"])
        if orders_pick and items_pick:
            orders_table, orders_df = orders_pick
            items_table, items_df = items_pick
            ocols = [str(c) for c in orders_df.columns]
            icols = [str(c) for c in items_df.columns]
            o_order_col = _pick_best_column(ocols, ["order_id", "order"])
            o_customer_col = _pick_best_column(ocols, ["customer_id", "customer", "client_id"])
            i_order_col = _pick_best_column(icols, ["order_id", "order"])
            qty_col = _pick_best_column(icols, ["quantity", "qty"])
            price_col = _pick_best_column(icols, ["list_price", "unit_price", "price", "amount"])
            discount_col = _pick_best_column(icols, ["discount"])
            if o_order_col and o_customer_col and i_order_col and qty_col and price_col:
                revenue_expr = (
                    f"(oi.{qty_col} * oi.{price_col} * (1 - COALESCE(oi.{discount_col}, 0)))"
                    if discount_col
                    else f"(oi.{qty_col} * oi.{price_col})"
                )
                return (
                    "WITH order_totals AS (\n"
                    f"  SELECT o.{o_customer_col} AS customer_id, o.{o_order_col} AS order_id, SUM({revenue_expr}) AS order_value\n"
                    f"  FROM {orders_table} o\n"
                    f"  JOIN {items_table} oi ON o.{o_order_col} = oi.{i_order_col}\n"
                    f"  GROUP BY o.{o_customer_col}, o.{o_order_col}\n"
                    ")\n"
                    "SELECT customer_id, AVG(order_value) AS avg_order_value, COUNT(order_id) AS order_count\n"
                    "FROM order_totals\n"
                    "GROUP BY customer_id\n"
                    "ORDER BY avg_order_value DESC\n"
                    "LIMIT 50"
                )

    return ""


def _run_text_generation(
    provider: str,
    system_prompt: str,
    user_message: str,
    ollama_endpoint: str,
    ollama_model: str,
    gemini_api_key: str,
    gemini_model: str,
) -> str:
    if provider == "gemini":
        return _query_gemini(
            gemini_api_key,
            gemini_model,
            system_prompt,
            user_message,
        )
    return _query_ollama(
        ollama_endpoint,
        ollama_model,
        system_prompt,
        user_message,
    )


def _repair_sql_with_ai(
    provider: str,
    question: str,
    failed_sql: str,
    error_message: str,
    schema_description: str,
    ollama_endpoint: str,
    ollama_model: str,
    gemini_api_key: str,
    gemini_model: str,
) -> str:
    system_prompt = (
        "You are a SQL repair engine for SQLite. "
        "Fix the SQL using the provided schema and execution error. "
        "Return ONLY corrected SQL SELECT text, with LIMIT 50 max."
    )
    user_message = (
        f"Question: {question}\n"
        f"Schema:\n{schema_description}\n\n"
        f"Failed SQL:\n{failed_sql}\n\n"
        f"Execution error:\n{error_message}\n\n"
        "Constraints:\n"
        "- SELECT only\n"
        "- Use existing table/column names only\n"
        "- No markdown or commentary"
    )
    return _run_text_generation(
        provider=provider,
        system_prompt=system_prompt,
        user_message=user_message,
        ollama_endpoint=ollama_endpoint,
        ollama_model=ollama_model,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
    ).strip()


def generate_query_from_email_with_ai(
    email_body: str,
    tables: Dict[str, pd.DataFrame],
    ai_provider: str = "ollama",
    ollama_endpoint: str = "http://localhost:11434",
    ollama_model: str = "llama2",
    gemini_api_key: str = "",
    gemini_model: str = "gemini-2.0-flash",
) -> str:
    if not email_body or not email_body.strip():
        return "No email body detected to process."
    
    if not tables:
        return "No database tables available for querying."
    
    question = email_body.strip()

    deterministic = _deterministic_agent_answer(question, tables)
    if deterministic:
        return deterministic
    
    schema_description = _build_schema_description(tables)
    
    system_prompt = f"""You are a senior analytics engineer. Given a user question and database schema, generate a safe SQL query that answers the question precisely.

Available database tables and columns:
{schema_description}

Rules:
1. Generate ONLY valid SQL SELECT statements
2. Always LIMIT results to 50 rows maximum
3. Use SQLite-compatible SQL syntax only
4. Return only SQL text; do not include markdown, explanations, or code fences
5. Use table and column names exactly as provided above
6. For date filtering, use SQLite date functions when needed
7. Include all explicitly requested attributes in SELECT. Example: if asked for "name, phone, email", include all three columns.
8. When user references a specific ID, include an exact WHERE filter for that ID.
9. Prefer explicit column names over SELECT *.
10. If aggregation is requested (highest month, totals), include correct GROUP BY/ORDER BY and clear aliases."""

    user_message = f"User question: {question}"
    
    try:
        provider_chain = _build_provider_chain(ai_provider, gemini_api_key)
        last_error = ""
        failure_log: List[str] = []

        # Rule-based planning first for predictable high-frequency analytics intents.
        rule_sql = _rule_based_sql_planner(question, tables)
        if rule_sql:
            artifact = _execute_generated_query_artifact(rule_sql, tables, question=question)
            if artifact.get("ok"):
                synthesized = _synthesize_email_answer_from_query_result(
                    question=question,
                    artifact=artifact,
                    primary_provider=provider_chain[0],
                    ai_provider=ai_provider,
                    ollama_endpoint=ollama_endpoint,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    gemini_model=gemini_model,
                )
                if synthesized:
                    return synthesized
                return str(artifact.get("summary_text") or "")
            failure_log.append(f"rule_sql_failed: {artifact.get('error', 'unknown execution failure')}")

        for provider in provider_chain:
            try:
                response_text = _run_text_generation(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    ollama_endpoint=ollama_endpoint,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    gemini_model=gemini_model,
                )

                generated_sql = response_text.strip()
                artifact = _execute_generated_query_artifact(generated_sql, tables, question=question)
                if not artifact.get("ok"):
                    last_error = str(artifact.get("error", "SQL execution failed"))
                    failure_log.append(f"{provider}:plan_failed:{last_error}")

                    repaired_sql = _repair_sql_with_ai(
                        provider=provider,
                        question=question,
                        failed_sql=generated_sql,
                        error_message=last_error,
                        schema_description=schema_description,
                        ollama_endpoint=ollama_endpoint,
                        ollama_model=ollama_model,
                        gemini_api_key=gemini_api_key,
                        gemini_model=gemini_model,
                    )
                    repaired_artifact = _execute_generated_query_artifact(repaired_sql, tables, question=question)
                    if not repaired_artifact.get("ok"):
                        last_error = str(repaired_artifact.get("error", "SQL repair execution failed"))
                        failure_log.append(f"{provider}:repair_failed:{last_error}")
                        continue

                    artifact = repaired_artifact

                synthesis = _synthesize_email_answer_from_query_result(
                    question=question,
                    artifact=artifact,
                    primary_provider=provider,
                    ai_provider=ai_provider,
                    ollama_endpoint=ollama_endpoint,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    gemini_model=gemini_model,
                )
                if synthesis:
                    return synthesis
                return str(artifact.get("summary_text") or "")
            except Exception as exc:
                last_error = str(exc)
                failure_log.append(f"{provider}:exception:{last_error}")
                continue

        if last_error:
            _log_event("warning", "AI SQL generation failed across providers; using deterministic fallback.", {"error": last_error})
        deterministic_fallback = answer_question_from_tables(question, tables)
        if "could not confidently map" not in deterministic_fallback.lower():
            return deterministic_fallback

        diag_tail = ""
        if failure_log:
            diag_tail = "\nTechnical note: " + " | ".join(failure_log[:3])
        return (
            "I could not execute a valid SQL plan for this question yet. "
            "Please retry with one extra detail like date range, store, or top-N constraint."
            + diag_tail
        )
    except Exception as e:
        fallback = answer_question_from_tables(question, tables)
        if "could not confidently map" in fallback.lower():
            return "I hit an orchestration error while planning this query. Please retry and include one extra filter or grouping hint."
        return fallback


def _build_schema_description(tables: Dict[str, pd.DataFrame]) -> str:
    description_parts = []
    for table_name, df in tables.items():
        cols_info = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            cols_info.append(f"  - {col} ({dtype})")
        cols_str = "\n".join(cols_info)
        description_parts.append(f"Table: {table_name}\nColumns:\n{cols_str}")
    return "\n\n".join(description_parts)


def _query_ollama(endpoint: str, model: str, system_prompt: str, user_message: str) -> str:
    import requests
    
    url = f"{endpoint}/api/generate"
    payload = {
        "model": model,
        "prompt": f"System: {system_prompt}\n\n{user_message}",
        "stream": False,
        "temperature": 0.2,
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except Exception as e:
        raise Exception(f"Ollama query failed: {str(e)}")


def _query_gemini(api_key: str, model: str, system_prompt: str, user_message: str) -> str:
    import requests
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt},
                    {"text": user_message}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500,
        },
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        if "candidates" in result and result["candidates"]:
            content = result["candidates"][0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        return "No response from Gemini"
    except Exception as e:
        raise Exception(f"Gemini query failed: {str(e)}")


def _extract_sql_candidate(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    fence_match = re.search(r"```(?:sql)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()

    select_match = re.search(r"(?is)\bselect\b[\s\S]*", raw)
    if not select_match:
        return ""

    sql = select_match.group(0).strip()
    if ";" in sql:
        sql = sql.split(";", 1)[0].strip()

    if " limit " not in f" {sql.lower()} ":
        sql = f"{sql} LIMIT 50"
    return sql


def _format_number_compact(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _format_query_result(question: str, result: pd.DataFrame) -> str:
    q = (question or "").lower()
    sales_query = any(token in q for token in ["sales", "revenue", "amount", "gmv", "total sales"])
    top_products_query = (
        any(token in q for token in ["top", "highest", "best", "most"]) and
        any(token in q for token in ["product", "item"]) and
        any(token in q for token in ["revenue", "sales", "amount", "gmv"])
    )

    if result.empty:
        return "I checked the dataset and found no matching records."

    if result.shape == (1, 1):
        value = result.iat[0, 0]
        if pd.isna(value):
            return "I checked the dataset and found no matching value."
        try:
            num = float(value)
            pretty = _format_number_compact(num)
            if sales_query:
                return f"Sales for the requested period is {pretty}."
            return f"The result is {pretty}."
        except Exception:
            return f"The result is {value}."

    if top_products_query:
        # For ranking-style requests, return a numbered summary instead of raw dataframe dump.
        candidate_name = _pick_best_column([str(c) for c in result.columns], ["product_name", "name", "item_name", "description", "product", "stockitemname"]) or str(result.columns[0])
        candidate_revenue = _pick_best_column([str(c) for c in result.columns], ["revenue", "sales", "amount", "total", "line_total", "value"]) or str(result.columns[-1])
        lines: List[str] = []
        for idx, (_, row) in enumerate(result.head(10).iterrows(), start=1):
            name_val = row.get(candidate_name, row.iloc[0] if len(row) else "unknown")
            rev_val = row.get(candidate_revenue, row.iloc[-1] if len(row) else 0)
            try:
                rev_txt = _format_number_compact(float(rev_val))
            except Exception:
                rev_txt = str(rev_val)
            lines.append(f"{idx}. {name_val} - {rev_txt}")
        return "Top products by revenue:\n" + "\n".join(lines)

    if len(result) == 1:
        row = result.iloc[0].to_dict()
        parts = [f"{k}: {v}" for k, v in row.items()]
        return "Here is the result: " + ", ".join(parts)

    head_n = min(5, len(result))
    columns = ", ".join([str(c) for c in result.columns])
    return (
        f"I found {len(result)} matching records.\n"
        f"Columns returned: {columns}.\n"
        f"Showing top {head_n}:\n\n{result.head(head_n).to_string(index=False)}"
    )


def _execute_generated_query_artifact(sql_text: str, tables: Dict[str, pd.DataFrame], question: str = "") -> Dict[str, Any]:
    sql = _extract_sql_candidate(sql_text)
    if not sql:
        return {
            "ok": False,
            "sql": "",
            "error": "No SQL candidate generated.",
        }

    lowered = sql.lower().strip()
    if not lowered.startswith("select"):
        return {
            "ok": False,
            "sql": sql,
            "error": "Only SELECT queries are allowed.",
        }
    if any(token in lowered for token in [" insert ", " update ", " delete ", " drop ", " alter ", " create ", " attach ", " detach ", " pragma ", ";", "--"]):
        return {
            "ok": False,
            "sql": sql,
            "error": "Blocked SQL pattern detected.",
        }

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        with engine.connect() as conn:
            for table_name, df in tables.items():
                df.to_sql(table_name, conn, if_exists="replace", index=False)

            result = pd.read_sql(sql, conn)
            head_n = min(10, len(result))
            preview_rows = result.head(head_n).to_dict(orient="records")
            return {
                "ok": True,
                "sql": sql,
                "row_count": int(len(result)),
                "columns": [str(c) for c in result.columns],
                "preview_rows": preview_rows,
                "summary_text": _format_query_result(question, result),
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "sql": sql,
            "error": f"SQL execution failed: {exc}",
        }


def _synthesize_email_answer_from_query_result(
    question: str,
    artifact: Dict[str, Any],
    primary_provider: str,
    ai_provider: str,
    ollama_endpoint: str,
    ollama_model: str,
    gemini_api_key: str,
    gemini_model: str,
) -> str:
    if not artifact.get("ok"):
        return ""

    row_count = int(artifact.get("row_count", 0) or 0)
    columns = artifact.get("columns", []) or []
    preview_rows = artifact.get("preview_rows", []) or []
    sql = str(artifact.get("sql", ""))
    summary_text = str(artifact.get("summary_text", ""))
    preview_json = json.dumps(preview_rows, ensure_ascii=True, default=str)

    system_prompt = (
        "You are an enterprise analytics email assistant. "
        "You must answer ONLY from the provided SQL result payload. "
        "Never invent rows, columns, totals, or entities not present in payload. "
        "If evidence is insufficient, explicitly say so and suggest a precise follow-up question."
    )
    user_message = (
        f"Question: {question}\n"
        f"Executed SQL: {sql}\n"
        f"Row count: {row_count}\n"
        f"Columns: {', '.join(columns)}\n"
        f"Preview rows (JSON): {preview_json}\n"
        "Reply in plain text with this structure:\n"
        "Answer: <direct answer>\n"
        "Evidence: <1-3 bullet points grounded in rows/columns>\n"
        "Confidence: High/Medium/Low\n"
        "Keep it concise and factual."
    )

    fallback_chain = _build_provider_chain(ai_provider, gemini_api_key)
    ordered_chain = [primary_provider] + [p for p in fallback_chain if p != primary_provider]

    for provider in ordered_chain:
        try:
            drafted = _run_text_generation(
                provider=provider,
                system_prompt=system_prompt,
                user_message=user_message,
                ollama_endpoint=ollama_endpoint,
                ollama_model=ollama_model,
                gemini_api_key=gemini_api_key,
                gemini_model=gemini_model,
            ).strip()
            if drafted and len(drafted) > 20:
                return drafted
        except Exception:
            continue

    return summary_text


def process_agent_inbox_once(
    agent_email: str,
    gmail_app_password: str,
    imap_host: str,
    smtp_host: str,
    smtp_port: int,
    tables: Dict[str, pd.DataFrame],
    max_messages_per_cycle: int = 5,
    ai_provider: str = "ollama",
    ollama_endpoint: str = "http://localhost:11434",
    ollama_model: str = "llama2",
    gemini_api_key: str = "",
    gemini_model: str = "gemini-2.0-flash",
) -> Dict:
    replied = 0
    processed = 0
    skipped = 0
    failures: List[str] = []

    imap_conn = None
    smtp_conn = None

    try:
        _log_event("debug", f"Attempting IMAP connection to {imap_host}...", {"imap_host": imap_host})
        imap_conn = imaplib.IMAP4_SSL(imap_host)
        _log_event("debug", f"IMAP connected. Logging in as {agent_email}...", {"agent_email": agent_email})
        imap_conn.login(agent_email, gmail_app_password)
        _log_event("debug", "IMAP login successful. Selecting INBOX...", {})
        imap_conn.select("INBOX")
        _log_event("debug", "Searching for unseen messages...", {})
        status, payload = imap_conn.search(None, "UNSEEN")
        if status != "OK":
            error_msg = f"IMAP search failed with status '{status}'"
            _log_event("error", error_msg, {"status": status})
            return {"processed": 0, "replied": 0, "skipped": 0, "failures": [error_msg]}

        message_ids = payload[0].split()
        unseen_count = len(message_ids)
        _log_event("info", f"Found {unseen_count} unseen message(s) in inbox.", {"unseen_count": unseen_count})
        selected_ids = list(reversed(message_ids))[:max_messages_per_cycle]

        _log_event("debug", f"Attempting SMTP connection to {smtp_host}:{smtp_port}...", {"smtp_host": smtp_host, "smtp_port": smtp_port})
        smtp_conn = smtplib.SMTP(smtp_host, int(smtp_port), timeout=30)
        _log_event("debug", "SMTP connected. Starting TLS...", {})
        smtp_conn.starttls()
        _log_event("debug", f"TLS started. Logging in as {agent_email}...", {"agent_email": agent_email})
        smtp_conn.login(agent_email, gmail_app_password)
        _log_event("debug", "SMTP login successful.", {})

        for message_id in selected_ids:
            processed += 1
            try:
                status, data = imap_conn.fetch(message_id, "(BODY.PEEK[])")
                if status != "OK" or not data or not data[0]:
                    skipped += 1
                    continue

                raw_bytes = data[0][1]
                msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
                sender = parseaddr(msg.get("From", ""))[1].strip().lower()
                if not sender:
                    skipped += 1
                    continue

                if sender == agent_email.lower():
                    imap_conn.store(message_id, "+FLAGS", "\\Seen")
                    skipped += 1
                    continue

                plain_text = _extract_plain_text(msg)
                question = _first_question_line(plain_text)
                if not question:
                    question = str(msg.get("Subject", "")).strip()

                response_text = generate_query_from_email_with_ai(
                    email_body=question,
                    tables=tables,
                    ai_provider=ai_provider,
                    ollama_endpoint=ollama_endpoint,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    gemini_model=gemini_model,
                )

                footer = (
                    "\n\nDisclaimer: This content in this email is AI-generated."
                    f"\n© {datetime.now(timezone.utc).year}, nexus intelligence"
                )
                final_body = response_text + footer
                final_body_html = (
                    f"<div style=\"white-space:pre-wrap;\">{response_text}</div>"
                    "<hr style=\"margin:16px 0;border:none;border-top:1px solid #e5e7eb;\"/>"
                    "<div style=\"color:#8a8a8a;font-size:12px;line-height:1.5;\">"
                    "Disclaimer: This content in this email is AI-generated.<br/>"
                    f"&copy; {datetime.now(timezone.utc).year}, <strong style=\"font-size:11px;\">nexus intelligence</strong>"
                    "</div>"
                )

                to_recipients, cc_recipients = _collect_reply_all_recipients(msg, agent_email)
                if not to_recipients and sender:
                    to_recipients = [sender]
                if not to_recipients and not cc_recipients:
                    skipped += 1
                    continue

                response = EmailMessage()
                subject = str(msg.get("Subject", "")).strip()
                response["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}" if subject else "Re: Your question"
                response["From"] = agent_email
                response["To"] = ", ".join(to_recipients)
                if cc_recipients:
                    response["Cc"] = ", ".join(cc_recipients)

                message_id_hdr = msg.get("Message-ID", "").strip()
                if message_id_hdr:
                    response["In-Reply-To"] = message_id_hdr
                    response["References"] = message_id_hdr

                response.set_content(final_body)
                response.add_alternative(final_body_html, subtype="html")
                smtp_conn.send_message(response)
                imap_conn.store(message_id, "+FLAGS", "\\Seen \\Answered")
                replied += 1
            except Exception as exc:
                message_id_text = message_id.decode(errors="ignore") if isinstance(message_id, (bytes, bytearray)) else str(message_id)
                failures.append(f"message_id={message_id_text}: {exc}")

        summary = {
            "unseen_count": unseen_count,
            "processed": processed,
            "replied": replied,
            "skipped": skipped,
            "failures": failures,
        }

        if replied > 0:
            _log_event("info", f"Agent replied to {replied} email(s).", summary)
        elif processed > 0:
            _log_event("info", "Agent checked inbox with no outgoing replies.", summary)

        if failures:
            _log_event("error", "Agent encountered inbox processing errors.", summary)

        return summary
    except Exception as exc:
        error_msg = f"Agent inbox processing failed: {exc}"
        _log_event("error", error_msg, {"exception": str(type(exc).__name__), "details": str(exc)})
        return {"processed": 0, "replied": 0, "skipped": 0, "failures": [error_msg]}
    finally:
        if smtp_conn is not None:
            try:
                smtp_conn.quit()
            except Exception:
                pass
        if imap_conn is not None:
            try:
                imap_conn.logout()
            except Exception:
                pass


@dataclass
class AgentLoopConfig:
    agent_email: str
    gmail_app_password: str
    imap_host: str
    smtp_host: str
    smtp_port: int
    interval_seconds: int
    max_messages_per_cycle: int
    ai_provider: str = "ollama"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


def run_agent_inbox_loop(stop_event: threading.Event, loop_config: AgentLoopConfig, tables: Dict[str, pd.DataFrame]) -> None:
    _log_event("info", "Agent auto-reply loop started.", {"agent_email": loop_config.agent_email})
    while not stop_event.is_set():
        try:
            process_agent_inbox_once(
                agent_email=loop_config.agent_email,
                gmail_app_password=loop_config.gmail_app_password,
                imap_host=loop_config.imap_host,
                smtp_host=loop_config.smtp_host,
                smtp_port=loop_config.smtp_port,
                tables=tables,
                max_messages_per_cycle=loop_config.max_messages_per_cycle,
                ai_provider=loop_config.ai_provider,
                ollama_endpoint=loop_config.ollama_endpoint,
                ollama_model=loop_config.ollama_model,
                gemini_api_key=loop_config.gemini_api_key,
                gemini_model=loop_config.gemini_model,
            )
        except Exception as exc:
            _log_event("error", "Agent loop execution failed.", {"error": str(exc)})

        wait_seconds = max(10, int(loop_config.interval_seconds))
        stop_event.wait(wait_seconds)

    _log_event("info", "Agent auto-reply loop stopped.", {"agent_email": loop_config.agent_email})
