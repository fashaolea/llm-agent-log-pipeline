"""storage/jsonl_store.py - Write records to JSONL and SQLite."""
import json, logging, sqlite3
from pathlib import Path
from typing import Any
logger = logging.getLogger(__name__)
CORE_COLUMNS = ["trace_id","timestamp","status","model","steps","latency_ms","_anomaly_reason"]

class JSONLStore:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, records: list[dict], filename: str) -> Path:
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as fh:
            for rec in records: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        logger.info(f"Wrote {len(records)} records -> {filepath}")
        return filepath

    def read(self, filename: str) -> list[dict]:
        records = []
        with open(self.output_dir / filename, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip(): records.append(json.loads(line))
        return records

    def write_to_sqlite(self, records: list[dict], db_filename: str, table: str = "traces") -> Path:
        db_path = self.output_dir / db_filename
        conn = sqlite3.connect(db_path)
        try:
            col_defs = " TEXT, ".join(CORE_COLUMNS) + " TEXT"
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs}, extra TEXT, PRIMARY KEY (trace_id))")
            conn.commit()
            rows = []
            for rec in records:
                core = [str(rec.get(c)) if rec.get(c) is not None else None for c in CORE_COLUMNS]
                extra = {k: v for k, v in rec.items() if k not in CORE_COLUMNS}
                rows.append(tuple(core) + (json.dumps(extra, ensure_ascii=False),))
            cols = CORE_COLUMNS + ["extra"]
            conn.executemany(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", rows)
            conn.commit()
            logger.info(f"Inserted {len(rows)} rows -> {db_path}")
        finally: conn.close()
        return db_path

    def query(self, db_filename: str, sql: str, params: tuple = ()) -> list[dict]:
        conn = sqlite3.connect(self.output_dir / db_filename)
        conn.row_factory = sqlite3.Row
        try: return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally: conn.close()
