import json
import re
from typing import Dict, List, Tuple

import requests


def ollama_get_models(endpoint: str) -> List[str]:
    try:
        res = requests.get(endpoint.rstrip("/") + "/api/tags", timeout=3)
        if res.status_code != 200:
            return []
        payload = res.json()
        models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        return models
    except requests.RequestException:
        return []


def _build_ai_brief_prompt(analysis: Dict) -> str:
    top_tables = sorted(analysis["table_profiles"], key=lambda x: x["quality_score"])[:4]
    issues = []
    for t in top_tables:
        issues.extend(t["issues"][:3])

    return f"""
You are an enterprise principal data architect.
Summarize this relational database assessment for engineering leadership.

Context:
- Source type: {analysis['source_type']}
- Tables: {len(analysis['table_profiles'])}
- Relationships discovered: {len(analysis['relationships'])}
- Average quality score: {analysis['avg_quality_score']}

Critical issues:
{chr(10).join('- ' + i for i in issues[:10]) if issues else '- No major issues detected in current sample.'}

Output format:
1) Executive Summary (max 5 bullets)
2) Top Risks (max 5 bullets)
3) 48-Hour Remediation Plan (max 5 bullets)
4) 30-Day Data Governance Plan (max 5 bullets)
"""


def test_ollama_connection(endpoint: str, timeout_seconds: int = 8) -> Tuple[bool, str, List[str]]:
    url = endpoint.rstrip("/") + "/api/tags"
    try:
        response = requests.get(url, timeout=timeout_seconds)
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


def test_gemini_connection(api_key: str, model: str = "gemini-1.5-flash", timeout_seconds: int = 12) -> Tuple[bool, str]:
    if not api_key.strip():
        return False, "Gemini API key is required."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
    payload = {
        "contents": [{"parts": [{"text": "Reply with only: OK"}]}],
        "generationConfig": {"temperature": 0},
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
        return True, f"Connected to Gemini model '{model}'."
    except requests.Timeout:
        return False, f"Gemini connection timed out after {timeout_seconds}s."
    except Exception as exc:
        return False, f"Gemini connection failed: {exc}"


def _generate_ollama_brief(analysis: Dict, model: str, endpoint: str, timeout_seconds: int = 120) -> str:
    prompt = _build_ai_brief_prompt(analysis)

    url = endpoint.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds)
    except requests.Timeout as exc:
        raise RuntimeError(
            f"Ollama request timed out after {timeout_seconds}s. Increase timeout or use a lighter model."
        ) from exc

    if response.status_code == 404:
        installed = ollama_get_models(endpoint)
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds)
    except requests.Timeout as exc:
        raise RuntimeError(f"Gemini request timed out after {timeout_seconds}s.") from exc

    response.raise_for_status()
    data = response.json() if response.content else {}
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def generate_ai_brief(
    analysis: Dict,
    model: str,
    endpoint: str,
    provider: str = "ollama",
    api_key: str = "",
    timeout_seconds: int = 120,
) -> str:
    selected_provider = (provider or "ollama").strip().lower()
    if selected_provider == "gemini":
        return _generate_gemini_brief(analysis, model=model, api_key=api_key, timeout_seconds=timeout_seconds)
    return _generate_ollama_brief(analysis, model=model, endpoint=endpoint, timeout_seconds=timeout_seconds)


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
