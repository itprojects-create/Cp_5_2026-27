import os
import json
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "log")
LOG_FILE = os.path.join(LOG_DIR, "audit_trace.log")

def log_audit_trace(finding_id: str, cwe: str, source_var: str, sink_api: str, evidence_path: list):
    """
    Writes a timestamped JSON-formatted trace to /data/log/audit_trace.log.
    Example: [TRACE] Node 42 -> FLOWS_TO -> Node 85 => CWE-321 CONFIRMED.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    
    trace_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "finding_id": finding_id,
        "cwe": cwe,
        "source_var": source_var,
        "sink_api": sink_api,
        "evidence_path": evidence_path,
        "message": f"[TRACE] {' -> FLOWS_TO -> '.join(evidence_path)} => {cwe} CONFIRMED."
    }
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_entry) + "\n")
    except Exception as e:
        print(f"Failed to write audit log: {e}")
