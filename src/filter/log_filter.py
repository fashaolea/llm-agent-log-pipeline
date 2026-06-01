"""filter/log_filter.py - Split records into valid/anomaly."""
import logging
from typing import Any
logger = logging.getLogger(__name__)
REQUIRED_FIELDS = ["input", "output", "status"]

class LogFilter:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.min_steps = cfg.get("min_steps", 1)
        self.max_steps = cfg.get("max_steps", 50)
        self.drop_all_fail = cfg.get("drop_all_tool_fail", True)
        self.required_fields = cfg.get("required_fields", REQUIRED_FIELDS)

    def filter(self, records: list[dict]) -> tuple[list[dict], list[dict]]:
        valid, anomalies = [], []
        for rec in records:
            reason = self._anomaly_reason(rec)
            if reason: rec["_anomaly_reason"] = reason; anomalies.append(rec)
            else: valid.append(rec)
        logger.info(f"Filter: {len(valid)} valid, {len(anomalies)} anomalies.")
        return valid, anomalies

    def _anomaly_reason(self, rec: dict) -> str | None:
        output = rec.get("output", "")
        if not isinstance(output, str) or not output.strip(): return "empty_output"
        missing = [f for f in self.required_fields if f != "output" and not rec.get(f)]
        if missing: return f"missing_fields:{','.join(missing)}"
        steps = rec.get("steps")
        if steps is not None:
            if steps < self.min_steps: return f"steps_too_low:{steps}"
            if steps > self.max_steps: return f"steps_loop_exceeded:{steps}"
        if self.drop_all_fail:
            tcs = rec.get("tool_calls", [])
            if tcs and self._all_tool_calls_failed(tcs): return "all_tool_calls_failed"
        return None

    @staticmethod
    def _all_tool_calls_failed(tool_calls: list[Any]) -> bool:
        if not tool_calls: return False
        statuses = [str(tc.get("status", tc.get("state","unknown"))).lower() for tc in tool_calls if isinstance(tc, dict)]
        return bool(statuses) and all(s in ("failed","error","timeout","invalid") for s in statuses)
