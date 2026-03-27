import json
import re
import time
from typing import Dict, List, Tuple

import requests


def _ollama_headers(api_key: str = "") -> Dict[str, str]:
    token = (api_key or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _normalize_gemini_model(model: str) -> str:
    normalized = (model or "").strip()
    return normalized or "gemini-2.0-flash"


def _list_gemini_models(api_key: str, timeout_seconds: int = 10) -> List[str]:
    if not api_key.strip():
        return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json() if response.content else {}
        raw_models = payload.get("models", []) if isinstance(payload, dict) else []
        model_names: List[str] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            if name.startswith("models/"):
                name = name.split("models/", 1)[1]
            model_names.append(name)
        return sorted(set(model_names))
    except Exception:
        return []


def _extract_gemini_error_message(response: requests.Response) -> str:
    try:
        payload = response.json() if response.content else {}
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = str(error.get("message", "")).strip()
        status = str(error.get("status", "")).strip()
        detail = f"{status}: {message}".strip(": ")
        if detail:
            return detail
    except Exception:
        pass

    text = (response.text or "").strip()
    if text:
        return text[:400]
    return f"HTTP {response.status_code}"


def _candidate_gemini_models(selected_model: str, api_key: str, timeout_seconds: int) -> List[str]:
    available = _list_gemini_models(api_key, timeout_seconds=timeout_seconds)
    if not available:
        return [selected_model]

    # Prefer broadly compatible generateContent models first.
    preferred = [selected_model, "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro", "gemini-2.0-flash"]
    ordered: List[str] = []
    for model in preferred + available:
        if model in available and model not in ordered:
            ordered.append(model)
    return ordered or [selected_model]


def ollama_get_models(endpoint: str, api_key: str = "", timeout_seconds: int = 8) -> List[str]:
    try:
        res = requests.get(
            endpoint.rstrip("/") + "/api/tags",
            timeout=timeout_seconds,
            headers=_ollama_headers(api_key),
        )
        if res.status_code != 200:
            return []
        payload = res.json()
        models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        return models
    except requests.RequestException:
        return []


def _build_ai_brief_prompt(analysis: Dict) -> str:
    table_profiles = analysis.get("table_profiles", []) if isinstance(analysis.get("table_profiles"), list) else []
    relationships = analysis.get("relationships", []) if isinstance(analysis.get("relationships"), list) else []

    source_type = analysis.get("source_type", "Unknown")
    avg_quality = analysis.get("avg_quality_score", 0)

    top_risk_tables = sorted(
        table_profiles,
        key=lambda x: float(x.get("quality_score", 0) or 0),
    )[:5]
    largest_tables = sorted(
        table_profiles,
        key=lambda x: int(x.get("estimated_total_rows", 0) or 0),
        reverse=True,
    )[:5]

    high_conf_relationships = [r for r in relationships if float(r.get("confidence", 0) or 0) >= 0.85]
    mid_conf_relationships = [r for r in relationships if 0.70 <= float(r.get("confidence", 0) or 0) < 0.85]
    low_conf_relationships = [r for r in relationships if float(r.get("confidence", 0) or 0) < 0.70]

    critical_issues = []
    for table in top_risk_tables:
        issues = table.get("issues", []) if isinstance(table.get("issues"), list) else []
        critical_issues.extend(issues[:5])

    largest_table_lines = []
    for item in largest_tables:
        largest_table_lines.append(
            f"- {item.get('table', 'unknown')}: rows={item.get('estimated_total_rows', 0)}, "
            f"cols={item.get('column_count', 0)}, quality={item.get('quality_score', 0)}"
        )

    risk_table_lines = []
    for item in top_risk_tables:
        risk_table_lines.append(
            f"- {item.get('table', 'unknown')}: quality={item.get('quality_score', 0)}, "
            f"completeness={item.get('completeness_score', 0)}, consistency={item.get('consistency_score', 0)}, "
            f"temporal_bonus={item.get('temporal_bonus_points', 0)}, duplicate_pk_records={item.get('duplicate_pk_records', 0)}"
        )

    relationship_examples = []
    for rel in relationships[:15]:
        relationship_examples.append(
            f"- {rel.get('child_table', '?')}.{rel.get('child_column', '?')} -> "
            f"{rel.get('parent_table', '?')}.{rel.get('parent_column', '?')} "
            f"(confidence={rel.get('confidence', 'n/a')})"
        )

    return f"""
You are a principal data architect and data platform reviewer preparing a board-ready technical assessment.

Your report must be extremely detailed, evidence-based, and useful for senior data engineers, architects, and governance leads.

Non-negotiable rules:
- Ground every claim in the provided analysis metrics.
- Quantify impacts whenever possible (tables affected, confidence bands, severity levels).
- If evidence is missing, explicitly state: "Insufficient evidence from sampled metadata."
- Do not use vague language; provide concrete technical observations and actions.

Assessment context:
- Source type: {source_type}
- Tables analyzed: {len(table_profiles)}
- Relationships inferred: {len(relationships)}
- Average quality score: {avg_quality}
- Relationship confidence split: high(>=0.85)={len(high_conf_relationships)}, mid(0.70-0.84)={len(mid_conf_relationships)}, low(<0.70)={len(low_conf_relationships)}

Largest tables:
{chr(10).join(largest_table_lines) if largest_table_lines else '- None'}

Highest-risk tables:
{chr(10).join(risk_table_lines) if risk_table_lines else '- None'}

Critical issues detected:
{chr(10).join('- ' + i for i in critical_issues[:20]) if critical_issues else '- No major issues detected in current sample.'}

Sample relationships:
{chr(10).join(relationship_examples) if relationship_examples else '- None'}

Output format (Markdown with these exact section headings):
1) Executive Summary
2) Technical Findings by Domain (schema integrity, key design, referential confidence, quality anomalies)
3) Risk Register (Severity, Probability, Blast Radius, Detection Signal, Mitigation)
4) Data Contract and Governance Gaps
5) 48-Hour Remediation Plan (with owner role and measurable acceptance criteria)
6) 30-Day Hardening Plan (automations, monitors, controls)
7) Confidence Notes and Known Uncertainties
8) KPI Delta Forecast (what quality or reliability gains are expected after fixes)
9) Validation SQL Pack (6-10 SQL checks to verify remediation)

Style expectations:
- Enterprise-grade, concise but deep.
- Use short paragraphs, bullet lists, and mini tables where useful.
- Avoid motivational phrasing; focus on technically rigorous recommendations.
"""


def test_ollama_connection(endpoint: str, timeout_seconds: int = 8, api_key: str = "") -> Tuple[bool, str, List[str]]:
    url = endpoint.rstrip("/") + "/api/tags"
    try:
        response = requests.get(url, timeout=timeout_seconds, headers=_ollama_headers(api_key))
        response.raise_for_status()
        payload = response.json() if response.content else {}
        models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        if models:
            return True, f"Connected to Ollama. Models detected: {len(models)}", models
        return True, "Connected to Ollama but no models were detected. Pull a model with: ollama pull <model>", []
    except requests.Timeout:
        return False, f"Ollama connection timed out after {timeout_seconds}s. Check if the model runtime is busy.", []
    except Exception as exc:
        return False, f"Ollama connection failed: {exc}", []


def test_gemini_connection(api_key: str, model: str = "gemini-2.0-flash", timeout_seconds: int = 12) -> Tuple[bool, str]:
    if not api_key.strip():
        return False, "Gemini API key is required."

    selected_model = _normalize_gemini_model(model)

    # Connectivity check should avoid generation requests so it does not consume model quotas.
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
    try:
        response = requests.get(url, timeout=timeout_seconds)
        if response.status_code == 429:
            return (
                False,
                f"Gemini rate limit/quota exceeded (429). {_extract_gemini_error_message(response)}",
            )
        if response.status_code >= 400:
            return False, f"Gemini connection failed: {_extract_gemini_error_message(response)}"

        response.raise_for_status()
        available = _list_gemini_models(api_key, timeout_seconds=timeout_seconds)
        if available and selected_model not in available:
            sample = ", ".join(available[:8])
            return (
                True,
                f"Gemini key is valid, but model '{selected_model}' is not listed for this key. Available models: {sample}",
            )
        return True, f"Connected to Gemini API. Model selected: '{selected_model}'."
    except requests.Timeout:
        return False, f"Gemini connection timed out after {timeout_seconds}s."
    except Exception as exc:
        return False, f"Gemini connection failed: {exc}"


def _generate_ollama_brief(
    analysis: Dict,
    model: str,
    endpoint: str,
    timeout_seconds: int = 120,
    api_key: str = "",
) -> str:
    prompt = _build_ai_brief_prompt(analysis)

    url = endpoint.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds, headers=_ollama_headers(api_key))
    except requests.Timeout as exc:
        raise RuntimeError(
            f"Ollama request timed out after {timeout_seconds}s. Increase timeout or use a lighter model."
        ) from exc

    if response.status_code == 404:
        installed = ollama_get_models(endpoint, api_key=api_key)
        installed_txt = ", ".join(installed) if installed else "none detected"
        raise RuntimeError(
            f"Model '{model}' not found in Ollama. Installed models: {installed_txt}. "
            "Pull a model with: ollama pull <model_name>."
        )

    response.raise_for_status()
    return response.json().get("response", "").strip()


def _generate_gemini_brief(analysis: Dict, model: str, api_key: str, timeout_seconds: int = 90) -> str:
    if not api_key.strip():
        raise RuntimeError("Gemini API key is required for Gemini provider.")

    prompt = _build_ai_brief_prompt(analysis)
    selected_model = _normalize_gemini_model(model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

    attempted: List[str] = []
    # Keep Gemini retries bounded so UI does not appear stuck for minutes.
    candidate_models = _candidate_gemini_models(selected_model, api_key, timeout_seconds=min(timeout_seconds, 12))[:3]
    hard_timeout = max(15, int(timeout_seconds))
    deadline = time.monotonic() + hard_timeout
    saw_timeout = False

    for candidate_model in candidate_models:
        attempted.append(candidate_model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={api_key.strip()}"

        for attempt in range(2):
            remaining = int(deadline - time.monotonic())
            if remaining <= 1:
                raise RuntimeError(
                    f"Gemini request timed out after {hard_timeout}s. Try a smaller model or increase timeout."
                )
            request_timeout = max(5, min(20, remaining))
            try:
                response = requests.post(url, json=payload, timeout=request_timeout)
            except requests.Timeout as exc:
                saw_timeout = True
                if attempt < 1:
                    continue
                break

            if response.status_code == 429:
                if attempt < 1:
                    retry_after_header = response.headers.get("Retry-After", "").strip()
                    try:
                        wait_seconds = max(1, int(float(retry_after_header))) if retry_after_header else (attempt + 1) * 2
                    except ValueError:
                        wait_seconds = (attempt + 1) * 2
                    remaining = int(deadline - time.monotonic())
                    if remaining <= 1:
                        break
                    time.sleep(min(wait_seconds, max(1, remaining - 1)))
                    continue

                # Try next model if the current one is quota-limited.
                break

            if response.status_code == 404:
                break

            if response.status_code >= 400:
                error_detail = _extract_gemini_error_message(response)
                lowered = error_detail.lower()

                # Some models are listed for the key but do not support generateContent.
                # In that case, try the next candidate model instead of failing immediately.
                if (
                    response.status_code == 400
                    and (
                        "interactions api" in lowered
                        or "invalid_argument" in lowered
                        or "does not support" in lowered
                        or "only supports" in lowered
                    )
                ):
                    break

                raise RuntimeError(f"Gemini request failed: {error_detail}")

            data = response.json() if response.content else {}
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates.")

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
            if not text:
                raise RuntimeError("Gemini returned an empty response.")
            return text

    tried = ", ".join(attempted)
    if saw_timeout:
        raise RuntimeError(
            f"Gemini request timed out after {hard_timeout}s across attempted models: {tried}."
        )
    raise RuntimeError(
        "Gemini generation could not be completed. "
        f"Attempted models: {tried}. The key is likely quota-limited for generation right now."
    )


def generate_ai_brief(
    analysis: Dict,
    model: str,
    endpoint: str,
    provider: str = "ollama",
    api_key: str = "",
    ollama_api_key: str = "",
    timeout_seconds: int = 120,
) -> str:
    selected_provider = (provider or "ollama").strip().lower()
    if selected_provider == "gemini":
        return _generate_gemini_brief(analysis, model=model, api_key=api_key, timeout_seconds=timeout_seconds)
    return _generate_ollama_brief(
        analysis,
        model=model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        api_key=ollama_api_key,
    )


def _extract_json_object(text: str) -> Dict:
    cleaned = text.strip()
    if not cleaned:
        return {}

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.S)
    if fence:
        cleaned = fence.group(1).strip()

    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first >= 0 and last > first:
        candidate = cleaned[first : last + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return {}
    return {}


def generate_ai_erd_layout_hints(
    table_profiles: List[Dict],
    relationships: List[Dict],
    model: str,
    endpoint: str,
) -> Dict:
    if not model:
        return {}

    table_names = sorted({p.get("table", "") for p in table_profiles if p.get("table")})
    if not table_names:
        return {}

    edge_lines = []
    for rel in relationships:
        parent = rel.get("parent_table", "")
        child = rel.get("child_table", "")
        parent_col = rel.get("parent_column", "")
        child_col = rel.get("child_column", "")
        if parent and child:
            edge_lines.append(f"{parent}.{parent_col} -> {child}.{child_col}")

    prompt = f"""
You are generating ERD layout hints only.

Tables:
{json.dumps(table_names)}

Relationships:
{json.dumps(edge_lines)}

Return STRICT JSON with this exact shape:
{{
  "table_order": ["table_a", "table_b"],
  "domain_hints": {{
    "table_a": "sales",
    "table_b": "production"
  }}
}}

Rules:
- table_order must only contain known table names.
- domain_hints values must be one of: sales, production, core, other.
- Do not output markdown.
"""

    try:
        url = endpoint.rstrip("/") + "/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        raw = response.json().get("response", "")
        parsed = _extract_json_object(raw)
        if not parsed:
            return {}

        order = parsed.get("table_order") if isinstance(parsed.get("table_order"), list) else []
        valid_order = []
        seen = set()
        allowed = set(table_names)
        for item in order:
            if not isinstance(item, str):
                continue
            if item not in allowed or item in seen:
                continue
            valid_order.append(item)
            seen.add(item)

        domain_hints_raw = parsed.get("domain_hints") if isinstance(parsed.get("domain_hints"), dict) else {}
        domain_hints: Dict[str, str] = {}
        for table, domain in domain_hints_raw.items():
            if not isinstance(table, str) or not isinstance(domain, str):
                continue
            if table not in allowed:
                continue
            normalized = domain.strip().lower()
            if normalized in {"sales", "production", "core", "other"}:
                domain_hints[table] = normalized

        if not valid_order and not domain_hints:
            return {}

        return {
            "table_order": valid_order,
            "domain_hints": domain_hints,
        }
    except Exception:
        return {}
