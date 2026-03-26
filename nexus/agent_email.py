from __future__ import annotations

import imaplib
import re
import smtplib
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from typing import Deque, Dict, List, Optional, Tuple

import pandas as pd


_EVENT_LOG: Deque[Dict] = deque(maxlen=200)
_EVENT_LOCK = threading.Lock()
_REPLY_TIMESTAMPS: Deque[datetime] = deque()
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REPLIES = 3
_CC_SUBJECT_KEYWORDS = [
    "db query",
    "nexus",
    "shop",
    "shops",
    "order",
    "orders",
    "employee",
    "employees",
    "sales",
    "revenue",
]


def _log_event(level: str, message: str, metadata: Optional[Dict] = None) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "metadata": metadata or {},
    }
    # Mirror events to stdout so backend CLI can be used as a live monitor.
    try:
        meta_text = f" | meta={event['metadata']}" if event["metadata"] else ""
        print(f"[agent-email][{event['level']}][{event['timestamp']}] {event['message']}{meta_text}", flush=True)
    except Exception:
        pass
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

    if not str(firebase_api_key or "").strip():
        return (
            False,
            "Firebase authentication failed: missing Firebase API key. Provide FIREBASE_API_KEY in backend env or set it in the Agent panel.",
            None,
        )
    
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
        if "Method doesn't allow unregistered callers" in error_msg:
            error_msg = "Firebase API key is missing or invalid for Identity Toolkit sign-in."
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


def _is_allowed_sender(sender_email: str, msg, agent_email: str, allowed_domain: str = "") -> bool:
    sender = (sender_email or "").strip().lower()
    if not sender:
        return False

    to_addresses = [a.strip().lower() for _, a in getaddresses([msg.get("To", "")]) if a.strip()]
    cc_addresses = [a.strip().lower() for _, a in getaddresses([msg.get("Cc", "")]) if a.strip()]
    agent_addr = (agent_email or "").strip().lower()

    agent_in_to = agent_addr in to_addresses
    agent_in_cc = agent_addr in cc_addresses

    if not agent_in_to and not agent_in_cc:
        return False

    if agent_in_to:
        return True

    # Only allow CC traffic from same-domain senders.
    if allowed_domain and sender.endswith("@" + allowed_domain.lower()):
        return True

    # For CC-only traffic, require a subject keyword to avoid random CC replies.
    subject = str(msg.get("Subject", "")).strip().lower()
    if subject and any(token in subject for token in _CC_SUBJECT_KEYWORDS):
        return True

    return False


def _is_supported_business_query(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False

    allowed_tokens = [
        "employee",
        "employees",
        "staff",
        "headcount",
        "sales",
        "revenue",
        "amount",
        "orders",
        "order",
        "invoice",
        "count",
        "how many",
        "last month",
        "total",
        "average",
        "avg",
    ]
    blocked_tokens = [
        "weather",
        "joke",
        "song",
        "poem",
        "story",
        "movie",
        "sports",
        "politics",
        "news",
        "recipe",
    ]

    if any(tok in q for tok in blocked_tokens):
        return False
    return any(tok in q for tok in allowed_tokens)


def _prune_and_count_recent_replies(now_utc: datetime) -> int:
    cutoff = now_utc.timestamp() - _RATE_LIMIT_WINDOW_SECONDS
    while _REPLY_TIMESTAMPS and _REPLY_TIMESTAMPS[0].timestamp() < cutoff:
        _REPLY_TIMESTAMPS.popleft()
    return len(_REPLY_TIMESTAMPS)


def _can_send_reply_now() -> Tuple[bool, int]:
    now_utc = datetime.now(timezone.utc)
    current = _prune_and_count_recent_replies(now_utc)
    return (current < _RATE_LIMIT_MAX_REPLIES, current)


def _record_reply_timestamp() -> None:
    now_utc = datetime.now(timezone.utc)
    _prune_and_count_recent_replies(now_utc)
    _REPLY_TIMESTAMPS.append(now_utc)


def _build_html_body(answer_text: str) -> str:
    year = datetime.now(timezone.utc).year
    safe_answer = (answer_text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    return (
        "<div style='font-family:Segoe UI, Arial, sans-serif; color:#111827; font-size:14px; line-height:1.6;'>"
        f"<p style='margin:0 0 12px 0'>{safe_answer}</p>"
        "<div style='margin-top:16px; padding-top:10px; border-top:1px solid #E5E7EB; color:#6B7280; font-size:12px;'>"
        "<p style='margin:0 0 4px 0;'>Disclaimer: This content in this email is AI-generated.</p>"
        f"<p style='margin:0;'>© {year}, nexus intelligence</p>"
        "</div></div>"
    )


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
    sales_words = ["sales", "revenue", "amount", "gmv", "order_total", "total"]

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

    if any(w in query for w in sales_words):
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
            if total >= 100000:
                return f"Sales for the requested period is {total / 100000:,.2f} Lakhs."
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
        if total >= 100000:
            return f"Sales for the requested period is {total / 100000:,.2f} Lakhs."
        return f"Sales for the requested period is {total:,.2f}."

    for table_name, frame in tables.items():
        if table_name.lower() in query and any(x in query for x in ["count", "how many", "number", "total records"]):
            return f"The `{table_name}` table currently has {int(len(frame.index))} rows in the analyzed dataset snapshot."

    return (
        "I could not confidently map this question to a supported metric intent. "
        "Try queries like 'how many employees are there today?' or 'what are the sales for the last month?'."
    )


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
    
    schema_description = _build_schema_description(tables)
    
    system_prompt = f"""You are a database query assistant. Given a user question and database schema, generate a safe SQL query.

Available database tables and columns:
{schema_description}

Rules:
1. Generate ONLY valid SQL SELECT statements
2. Always LIMIT results to 50 rows maximum
3. Use SQLite-compatible SQL syntax only
4. Return only SQL text; do not include markdown, explanations, or code fences
5. Use table and column names exactly as provided above
6. For date filtering, use SQLite date functions when needed"""

    user_message = f"User question: {question}"
    
    try:
        if ai_provider == "gemini":
            response_text = _query_gemini(
                gemini_api_key,
                gemini_model,
                system_prompt,
                user_message
            )
        else:
            response_text = _query_ollama(
                ollama_endpoint,
                ollama_model,
                system_prompt,
                user_message
            )
        
        generated_sql = response_text.strip()
        result = _execute_generated_query(generated_sql, tables, question=question)
        return result
    except Exception as e:
        fallback = answer_question_from_tables(question, tables)
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


def _format_number_compact(value: float, use_lakhs: bool = False) -> str:
    if use_lakhs and abs(value) >= 100000:
        return f"{value / 100000:,.2f} Lakhs"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _format_query_result(question: str, result: pd.DataFrame) -> str:
    q = (question or "").lower()
    sales_query = any(token in q for token in ["sales", "revenue", "amount", "gmv", "total sales"])

    if result.empty:
        return "I checked the dataset and found no matching records."

    if result.shape == (1, 1):
        value = result.iat[0, 0]
        if pd.isna(value):
            return "I checked the dataset and found no matching value."
        try:
            num = float(value)
            pretty = _format_number_compact(num, use_lakhs=sales_query)
            if sales_query:
                return f"Sales for the requested period is {pretty}."
            return f"The result is {pretty}."
        except Exception:
            return f"The result is {value}."

    if len(result) == 1:
        row = result.iloc[0].to_dict()
        parts = [f"{k}: {v}" for k, v in row.items()]
        return "Here is the result: " + ", ".join(parts)

    head_n = min(5, len(result))
    return f"I found {len(result)} matching records. Showing top {head_n}:\n\n{result.head(head_n).to_string(index=False)}"


def _execute_generated_query(sql_text: str, tables: Dict[str, pd.DataFrame], question: str = "") -> str:
    sql = _extract_sql_candidate(sql_text)
    if not sql:
        return answer_question_from_tables(question, tables)

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
            return _format_query_result(question, result)
    except Exception:
        return answer_question_from_tables(question, tables)


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
    rate_limited = 0
    blocked_by_policy = 0
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

        # Fallback: if no unseen messages are found, inspect a small recent window.
        # This helps diagnose mails that were auto-marked seen by clients/filters.
        if unseen_count == 0:
            _log_event("debug", "No unseen messages found. Falling back to recent inbox scan.", {})
            all_status, all_payload = imap_conn.search(None, "ALL")
            if all_status == "OK":
                all_ids = all_payload[0].split()
                message_ids = all_ids[-max_messages_per_cycle:] if all_ids else []
                _log_event(
                    "info",
                    f"Fallback selected {len(message_ids)} recent message(s) for inspection.",
                    {"selected_recent_count": len(message_ids), "total_all_count": len(all_ids)},
                )
            else:
                _log_event("warning", "Fallback ALL search failed; continuing with unseen-only list.", {"status": all_status})

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
                    _log_event("warning", "Skipping message due to failed fetch payload.", {"message_id": str(message_id), "status": status})
                    skipped += 1
                    continue

                raw_bytes = data[0][1]
                msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
                sender = parseaddr(msg.get("From", ""))[1].strip().lower()
                msg_subject = str(msg.get("Subject", "")).strip()
                to_header = str(msg.get("To", "")).strip()
                cc_header = str(msg.get("Cc", "")).strip()

                _log_event(
                    "debug",
                    "Fetched candidate message.",
                    {
                        "message_id": str(message_id),
                        "from": sender,
                        "to": to_header,
                        "cc": cc_header,
                        "subject": msg_subject,
                    },
                )

                if not sender:
                    _log_event("warning", "Skipping message with empty sender.", {"message_id": str(message_id), "subject": msg_subject})
                    skipped += 1
                    continue

                if sender == agent_email.lower():
                    imap_conn.store(message_id, "+FLAGS", "\\Seen")
                    _log_event("debug", "Skipping self-sent message.", {"message_id": str(message_id), "sender": sender})
                    skipped += 1
                    continue

                if not _is_allowed_sender(sender, msg, agent_email, allowed_domain="burplefolk.com"):
                    _log_event(
                        "warning",
                        "Policy skip: sender not authorized for auto-reply.",
                        {
                            "message_id": str(message_id),
                            "sender": sender,
                            "to": to_header,
                            "cc": cc_header,
                            "agent_email": agent_email,
                            "subject": msg_subject,
                            "cc_subject_keywords": _CC_SUBJECT_KEYWORDS,
                        },
                    )
                    blocked_by_policy += 1
                    skipped += 1
                    continue

                plain_text = _extract_plain_text(msg)
                question = _first_question_line(plain_text)
                if not question:
                    question = str(msg.get("Subject", "")).strip()

                if not _is_supported_business_query(question):
                    _log_event(
                        "warning",
                        "Policy skip: unsupported/non-business query intent.",
                        {"message_id": str(message_id), "sender": sender, "question": question[:200]},
                    )
                    blocked_by_policy += 1
                    skipped += 1
                    continue

                can_send, in_window_count = _can_send_reply_now()
                if not can_send:
                    _log_event(
                        "warning",
                        "Rate limit reached: skipping reply to protect account.",
                        {
                            "message_id": str(message_id),
                            "sender": sender,
                            "window_seconds": _RATE_LIMIT_WINDOW_SECONDS,
                            "max_replies": _RATE_LIMIT_MAX_REPLIES,
                            "current_replies": in_window_count,
                        },
                    )
                    rate_limited += 1
                    skipped += 1
                    continue

                response_text = generate_query_from_email_with_ai(
                    email_body=question,
                    tables=tables,
                    ai_provider=ai_provider,
                    ollama_endpoint=ollama_endpoint,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    gemini_model=gemini_model,
                )

                final_body = response_text
                html_body = _build_html_body(response_text)

                to_recipients, cc_recipients = _collect_reply_all_recipients(msg, agent_email)
                _log_event(
                    "debug",
                    "Computed reply-all recipients.",
                    {
                        "message_id": str(message_id),
                        "to_recipients": to_recipients,
                        "cc_recipients": cc_recipients,
                        "sender": sender,
                    },
                )
                if not to_recipients and sender:
                    to_recipients = [sender]
                if not to_recipients and not cc_recipients:
                    _log_event("warning", "Skipping message with no computed recipients.", {"message_id": str(message_id), "sender": sender})
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
                response.add_alternative(html_body, subtype="html")
                smtp_conn.send_message(response)
                _record_reply_timestamp()
                imap_conn.store(message_id, "+FLAGS", "\\Seen \\Answered")
                _log_event(
                    "info",
                    "Reply sent successfully.",
                    {
                        "message_id": str(message_id),
                        "subject": response.get("Subject", ""),
                        "to": response.get("To", ""),
                        "cc": response.get("Cc", ""),
                    },
                )
                replied += 1
            except Exception as exc:
                message_id_text = message_id.decode(errors="ignore") if isinstance(message_id, (bytes, bytearray)) else str(message_id)
                failures.append(f"message_id={message_id_text}: {exc}")
                _log_event("error", "Failed processing message.", {"message_id": message_id_text, "error": str(exc)})

        summary = {
            "unseen_count": unseen_count,
            "processed": processed,
            "replied": replied,
            "skipped": skipped,
            "rate_limited": rate_limited,
            "blocked_by_policy": blocked_by_policy,
            "reply_limit_per_minute": _RATE_LIMIT_MAX_REPLIES,
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
