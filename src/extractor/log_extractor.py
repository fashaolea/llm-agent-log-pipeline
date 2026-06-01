"""
extractor/log_extractor.py
--------------------------
Extract Trajectory Trace records from raw JSONL logs.
Supports single JSONL file or directory batch processing.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FIELD_ALIASES: dict[str, list[str]] = {
    "trace_id":   ["trace_id", "run_id", "session_id", "id"],
    "timestamp":  ["timestamp", "ts", "created_at", "time"],
    "input":      ["input", "user_input", "query", "prompt"],
    "output":     ["output", "response", "answer", "result"],
    "tool_calls": ["tool_calls", "actions", "function_calls", "tools_used"],
    "steps":      ["steps", "turns", "iterations", "num_steps"],
    "status":     ["status", "state", "final_status"],
    "error":      ["error", "error_msg", "exception", "failure_reason"],
    "model":      ["model", "model_name", "llm"],
    "latency_ms": ["latency_ms", "duration_ms", "elapsed_ms", "latency"],
}


class LogExtractor:
    """Extract Agent run logs from JSONL files/directories."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def extract(self, input_path: str) -> list[dict[str, Any]]:
        path = Path(input_path)
        files = list(path.glob("**/*.jsonl")) if path.is_dir() else [path]
        if not files:
            raise FileNotFoundError(f"No .jsonl files found at: {input_path}")
        records: list[dict] = []
        for f in files:
            loaded = self._load_jsonl(f)
            records.extend(loaded)
        logger.info(f"Extracted {len(records)} total records from {len(files)} file(s).")
        return records

    def _load_jsonl(self, filepath: Path) -> list[dict]:
        records = []
        with open(filepath, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    record = self._normalize_fields(raw)
                    record["_source_file"] = filepath.name
                    record["_source_line"] = line_no
                    records.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse error at {filepath.name}:{line_no}: {e}")
        return records

    def _normalize_fields(self, raw: dict) -> dict:
        record: dict[str, Any] = {}
        for canonical, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                if alias in raw:
                    record[canonical] = raw[alias]
                    break
        known = {a for aliases in FIELD_ALIASES.values() for a in aliases}
        for k, v in raw.items():
            if k not in known and k not in record:
                record[f"raw_{k}"] = v
        return record

    @staticmethod
    def extract_json_blocks(text: str) -> list[dict]:
        pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', re.DOTALL)
        blocks = []
        for match in pattern.finditer(text):
            try:
                blocks.append(json.loads(match.group()))
            except json.JSONDecodeError:
                pass
        return blocks
