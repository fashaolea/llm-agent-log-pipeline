"""analyzer/tool_call_analyzer.py - Analyze tool call stats."""
import json, logging
from collections import Counter
from pathlib import Path
from typing import Any
import pandas as pd
logger = logging.getLogger(__name__)

FAILURE_TYPE_KEYWORDS = {
    "missing_parameter":    ["missing","required","param","argument"],
    "timeout":              ["timeout","timed out","time_exceeded"],
    "invalid_return_format":["invalid_json","parse_error","format","decode"],
    "invalid_retrieval":    ["no_result","empty_result","retrieval_fail","not_found"],
    "loop_failure":         ["max_steps","loop","recursion","exceeded_limit"],
}

def classify_failure(reason: str) -> str:
    if not reason: return "unknown"
    r = reason.lower()
    for ftype, kws in FAILURE_TYPE_KEYWORDS.items():
        if any(kw in r for kw in kws): return ftype
    return "other"

class ToolCallAnalyzer:
    def analyze(self, records: list[dict]) -> dict[str, Any]:
        total_calls = success_calls = 0
        failure_reasons, steps_list, anomaly_reasons = [], [], []
        for rec in records:
            steps = rec.get("steps")
            if isinstance(steps, int) and steps > 0: steps_list.append(steps)
            ar = rec.get("_anomaly_reason")
            if ar: anomaly_reasons.append(ar)
            for tc in rec.get("tool_calls", []):
                if not isinstance(tc, dict): continue
                total_calls += 1
                status = str(tc.get("status", tc.get("state",""))).lower()
                if status in ("success","ok","completed","done"): success_calls += 1
                else: failure_reasons.append(str(tc.get("error", tc.get("error_msg", status))))
        success_rate = (success_calls / total_calls) if total_calls > 0 else 0.0
        failure_types = [classify_failure(r) for r in failure_reasons]
        failure_counter = Counter(failure_types)
        total_failures = sum(failure_counter.values())
        failure_ratio = {k: round(v/total_failures, 4) for k, v in failure_counter.items()} if total_failures > 0 else {}
        avg_steps = (sum(steps_list)/len(steps_list)) if steps_list else 0.0
        return {
            "total_records": len(records), "total_tool_calls": total_calls,
            "success_calls": success_calls, "failed_calls": total_calls - success_calls,
            "success_rate": round(success_rate, 4),
            "failure_type_counts": dict(failure_counter),
            "failure_type_ratio": failure_ratio,
            "avg_steps": round(avg_steps, 2),
            "top_failure": failure_counter.most_common(1)[0][0] if failure_counter else "N/A",
            "anomaly_reason_counts": dict(Counter(anomaly_reasons)),
        }

    def to_dataframe(self, records: list[dict]) -> pd.DataFrame:
        rows = []
        for rec in records:
            base = {"trace_id": rec.get("trace_id",""), "status": rec.get("status",""),
                    "steps": rec.get("steps"), "model": rec.get("model",""),
                    "anomaly_reason": rec.get("_anomaly_reason",""),
                    "tool_call_count": len(rec.get("tool_calls",[]))}
            for tc in rec.get("tool_calls",[]):
                if isinstance(tc, dict):
                    row = base.copy()
                    row.update({"tool_name": tc.get("name",""), "tool_status": tc.get("status",""),
                                "tool_error": tc.get("error",""),
                                "failure_type": classify_failure(str(tc.get("error","")))})
                    rows.append(row)
            if not rec.get("tool_calls"): rows.append(base)
        return pd.DataFrame(rows)

    def save_report(self, analysis: dict, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(analysis, fh, ensure_ascii=False, indent=2)
        logger.info(f"Analysis report saved -> {path}")
