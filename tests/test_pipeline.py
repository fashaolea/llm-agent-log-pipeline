"""tests/test_pipeline.py - 13 unit tests for all modules."""
import json
from pathlib import Path
import pytest
from src.extractor.log_extractor import LogExtractor
from src.cleaner.log_cleaner import LogCleaner
from src.filter.log_filter import LogFilter
from src.storage.jsonl_store import JSONLStore
from src.analyzer.tool_call_analyzer import ToolCallAnalyzer, classify_failure

SAMPLE = [
    {"trace_id":"t1","input":"hello","output":"world","status":"success","steps":2,
     "tool_calls":[{"name":"search","status":"success"}]},
    {"trace_id":"t2","input":"query","output":"","status":"failed","steps":1,
     "tool_calls":[{"name":"db","status":"failed","error":"timeout: 30s"}]},
    {"trace_id":"t3","input":"email user@example.com key sk-abc1234567890xyz","output":"sent","status":"success","steps":1},
    {"trace_id":"t1","input":"dup","output":"dup","status":"success","steps":1},
    {"trace_id":"t4","input":"loop","output":"exceeded","status":"failed","steps":999,
     "tool_calls":[{"name":"fn","status":"failed","error":"max_steps exceeded loop"}]},
]

@pytest.fixture
def sample_jsonl(tmp_path):
    f = tmp_path / "s.jsonl"
    with open(f,"w") as fh:
        for r in SAMPLE: fh.write(json.dumps(r)+"\n")
    return f

class TestLogExtractor:
    def test_count(self, sample_jsonl):
        assert len(LogExtractor().extract(str(sample_jsonl))) == len(SAMPLE)
    def test_normalize(self):
        rec = LogExtractor()._normalize_fields({"run_id":"r1","user_input":"hi","response":"ok","state":"success","turns":3})
        assert rec["trace_id"]=="r1" and rec["input"]=="hi" and rec["steps"]==3

class TestLogCleaner:
    def test_dedup(self, sample_jsonl):
        cleaned = LogCleaner().clean(LogExtractor().extract(str(sample_jsonl)))
        assert [r.get("trace_id") for r in cleaned].count("t1") == 1
    def test_pii_email(self):
        r = {"trace_id":"x","input":"to user@example.com","output":"ok","status":"ok"}
        c = LogCleaner().clean([r])
        assert "[REDACTED_EMAIL]" in c[0]["input"]
    def test_pii_api_key(self):
        r = {"trace_id":"x","input":"sk-abc1234567890xyz","output":"ok","status":"ok"}
        c = LogCleaner().clean([r])
        assert "sk-abc1234567890xyz" not in c[0]["input"]
    def test_truncate(self):
        r = {"trace_id":"x","input":" ".join(f"w{i}" for i in range(20)),"output":"ok","status":"ok"}
        c = LogCleaner({"max_tokens":5}).clean([r])
        assert len(c[0]["input"].split())==5 and c[0].get("_input_truncated")

class TestLogFilter:
    def test_empty_output(self):
        recs=[{"trace_id":"a","input":"q","output":"","status":"f"},{"trace_id":"b","input":"q","output":"ok","status":"ok"}]
        valid,anoms=LogFilter().filter(recs)
        assert len(valid)==1 and "empty_output" in anoms[0]["_anomaly_reason"]
    def test_loop(self, sample_jsonl):
        cleaned=LogCleaner().clean(LogExtractor().extract(str(sample_jsonl)))
        _,anoms=LogFilter({"max_steps":50}).filter(cleaned)
        assert any("loop_exceeded" in r.get("_anomaly_reason","") for r in anoms)

class TestJSONLStore:
    def test_roundtrip(self, tmp_path):
        s=JSONLStore(tmp_path); recs=[{"trace_id":"x","v":1}]
        s.write(recs,"t.jsonl"); assert s.read("t.jsonl")==recs
    def test_sqlite(self, tmp_path):
        s=JSONLStore(tmp_path); s.write_to_sqlite([{"trace_id":"db1","status":"ok"}],"t.db")
        assert s.query("t.db","SELECT trace_id FROM traces")[0]["trace_id"]=="db1"

class TestAnalyzer:
    def test_success_rate(self):
        r=[{"tool_calls":[{"status":"success"},{"status":"success"},{"status":"failed","error":"timeout"}]}]
        res=ToolCallAnalyzer().analyze(r)
        assert res["total_tool_calls"]==3 and res["success_calls"]==2
    def test_classify(self):
        assert classify_failure("timeout: 30s")=="timeout"
        assert classify_failure("missing param")=="missing_parameter"
        assert classify_failure("invalid_json")=="invalid_return_format"
        assert classify_failure("max_steps loop")=="loop_failure"
        assert classify_failure("no_result")=="invalid_retrieval"
    def test_avg_steps(self):
        r=[{"steps":2,"tool_calls":[]},{"steps":4,"tool_calls":[]},{"steps":6,"tool_calls":[]}]
        assert ToolCallAnalyzer().analyze(r)["avg_steps"]==4.0
