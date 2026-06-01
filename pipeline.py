"""
LLM / Agent 运行日志清洗与分析 Pipeline
========================================
面向 Agent 运行日志、工具调用记录和错误案例，
实现 extract → clean → filter → store 的完整数据处理流程。

技术栈: Python, Pandas, Regex, JSONL, SQL, Git
"""

import argparse
import logging
from pathlib import Path

from src.extractor.log_extractor import LogExtractor
from src.cleaner.log_cleaner import LogCleaner
from src.filter.log_filter import LogFilter
from src.storage.jsonl_store import JSONLStore
from src.analyzer.tool_call_analyzer import ToolCallAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("pipeline")


def run_pipeline(input_path: str, output_dir: str, config: dict) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stats = {}

    logger.info("Step 1/4 - Extracting trajectory traces from raw logs...")
    extractor = LogExtractor(config.get("extractor", {}))
    raw_records = extractor.extract(input_path)
    stats["extracted"] = len(raw_records)

    logger.info("Step 2/4 - Cleaning: field parsing, dedup, truncation, masking...")
    cleaner = LogCleaner(config.get("cleaner", {}))
    cleaned_records = cleaner.clean(raw_records)
    stats["after_clean"] = len(cleaned_records)
    stats["clean_dropped"] = stats["extracted"] - stats["after_clean"]

    logger.info("Step 3/4 - Filtering: invalid outputs, anomaly samples...")
    log_filter = LogFilter(config.get("filter", {}))
    filtered_records, anomaly_records = log_filter.filter(cleaned_records)
    stats["after_filter"] = len(filtered_records)
    stats["anomalies"] = len(anomaly_records)

    logger.info("Step 4/4 - Storing normalized JSONL samples...")
    store = JSONLStore(output_path)
    store.write(filtered_records, "valid_samples.jsonl")
    store.write(anomaly_records, "anomaly_samples.jsonl")
    store.write_to_sqlite(filtered_records, "agent_logs.db", "traces")
    stats["stored"] = stats["after_filter"]

    logger.info("Analyzing tool call statistics...")
    analyzer = ToolCallAnalyzer()
    analysis = analyzer.analyze(filtered_records + anomaly_records)
    stats["analysis"] = analysis
    analyzer.save_report(analysis, output_path / "tool_call_report.json")

    logger.info("Pipeline complete.")
    print(f"\n{'='*55}")
    print(f"  Extracted: {stats.get('extracted',0):,}")
    print(f"  After clean: {stats.get('after_clean',0):,} (-{stats.get('clean_dropped',0):,})")
    print(f"  Valid samples: {stats.get('after_filter',0):,}")
    print(f"  Anomaly samples: {stats.get('anomalies',0):,}")
    print(f"  Tool call success rate: {analysis.get('success_rate',0):.1%}")
    print(f"  Avg task steps: {analysis.get('avg_steps',0):.2f}")
    print(f"{'='*55}\n")
    return stats


def main():
    parser = argparse.ArgumentParser(description="LLM Agent Log Cleaning & Analysis Pipeline")
    parser.add_argument("--input", required=True, help="Raw log path or dir")
    parser.add_argument("--output", default="data/output", help="Output directory")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--min-steps", type=int, default=1)
    args = parser.parse_args()
    config = {
        "extractor": {},
        "cleaner": {"max_tokens": args.max_tokens},
        "filter": {"min_steps": args.min_steps},
    }
    run_pipeline(args.input, args.output, config)


if __name__ == "__main__":
    main()
