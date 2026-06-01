"""
cleaner/log_cleaner.py - Clean extracted records:
dedup, truncation, PII masking, anomaly marking.
"""
import hashlib, logging, re
from typing import Any

logger = logging.getLogger(__name__)

SENSITIVE_PATTERNS = {
    "api_key":  re.compile(r'(?i)(sk|pk|api[-_]?key)[-_]?[A-Za-z0-9]{16,}'),
    "email":    re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'),
    "phone_cn": re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'),
    "ip_addr":  re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "bearer":   re.compile(r'(?i)bearer\s+[A-Za-z0-9\-.~+/]+=*'),
    "password": re.compile(r'(?i)"?password"?\s*[:=]\s*"?[^\s"]{4,}"?'),
}
PLACEHOLDER = {
    "api_key": "[REDACTED_API_KEY]", "email": "[REDACTED_EMAIL]",
    "phone_cn": "[REDACTED_PHONE]", "ip_addr": "[REDACTED_IP]",
    "bearer": "[REDACTED_TOKEN]", "password": "[REDACTED_PASSWORD]",
}

class LogCleaner:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.max_tokens  = cfg.get("max_tokens", 2048)
        self.dedup_field = cfg.get("dedup_field", "trace_id")
        self.mask_pii    = cfg.get("mask_pii", True)

    def clean(self, records: list[dict]) -> list[dict]:
        seen_ids, seen_hashes, cleaned = set(), set(), []
        for rec in records:
            rec = self._fix_types(rec)
            rec = self._truncate(rec)
            if self.mask_pii:
                rec = self._mask_sensitive(rec)
            uid = self._get_uid(rec, seen_ids, seen_hashes)
            if uid is None:
                rec["_drop_reason"] = "duplicate"
                continue
            cleaned.append(rec)
        logger.info(f"Cleaned: {len(cleaned)} kept, {len(records)-len(cleaned)} dropped.")
        return cleaned

    def _fix_types(self, rec: dict) -> dict:
        for f in ("steps", "latency_ms"):
            if f in rec:
                try: rec[f] = int(rec[f])
                except: rec[f] = None
        if "tool_calls" in rec and not isinstance(rec["tool_calls"], list):
            rec["tool_calls"] = []
        if "status" in rec and isinstance(rec["status"], str):
            rec["status"] = rec["status"].lower().strip()
        return rec

    def _truncate(self, rec: dict) -> dict:
        for field in ("input", "output"):
            if field in rec and isinstance(rec[field], str):
                tokens = rec[field].split()
                if len(tokens) > self.max_tokens:
                    rec[field] = " ".join(tokens[:self.max_tokens])
                    rec[f"_{field}_truncated"] = True
        return rec

    def _mask_sensitive(self, rec: dict) -> dict:
        def _mask_str(text: str) -> str:
            for name, pattern in SENSITIVE_PATTERNS.items():
                text = pattern.sub(PLACEHOLDER[name], text)
            return text
        def _mask_value(v: Any) -> Any:
            if isinstance(v, str): return _mask_str(v)
            if isinstance(v, dict): return {k: _mask_value(val) for k, val in v.items()}
            if isinstance(v, list): return [_mask_value(i) for i in v]
            return v
        return {k: _mask_value(v) for k, v in rec.items()}

    def _get_uid(self, rec, seen_ids, seen_hashes):
        tid = rec.get(self.dedup_field)
        if tid:
            if tid in seen_ids: return None
            seen_ids.add(tid); return str(tid)
        content = f"{rec.get('input','')}{rec.get('output','')}"
        h = hashlib.md5(content.encode()).hexdigest()
        if h in seen_hashes: return None
        seen_hashes.add(h); rec["_content_hash"] = h; return h
