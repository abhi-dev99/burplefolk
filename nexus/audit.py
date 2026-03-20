import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from .models import AUDIT_FILE


def audit_load() -> List[Dict]:
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def audit_commit(payload: Dict, actor: str = "Team") -> Dict:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    hash_value = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "artifact": "analysis_snapshot",
        "tables": len(payload.get("table_profiles", [])),
        "relationships": len(payload.get("relationships", [])),
        "hash": hash_value,
        "status": "locked",
    }
    ledger = audit_load()
    ledger.append(entry)
    with open(AUDIT_FILE, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)
    return entry
