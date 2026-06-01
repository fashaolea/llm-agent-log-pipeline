# LLM / Agent 运行日志清洗与分析 Pipeline

**数据管道 / 可观测性基础**

面向 Agent 运行日志、工具调用记录和错误案例，实现完整的
**extract → clean → filter → store** 数据处理流程。

---

## 项目背景

随着 LLM Agent 在生产环境中的大规模部署，运行日志（Trajectory Trace）的质量
直接影响后续的评估、微调和问题排查效率。

## 技术栈

Python 3.11+, Pandas, Regex, JSONL, SQLite, Git

## 快速开始

```bash
pip install -r requirements.txt
python pipeline.py --input data/raw/sample_agent_logs.jsonl --output data/output
pytest tests/ -v
```

## 目录结构

```
src/extractor/log_extractor.py   # 字段提取与别名统一
src/cleaner/log_cleaner.py       # 去重、截断、PII脱敏
src/filter/log_filter.py         # 有效/异常样本分离
src/storage/jsonl_store.py       # JSONL + SQLite
src/analyzer/tool_call_analyzer.py  # 工具调用统计
tests/test_pipeline.py           # 13个单元测试
```

## 工具调用失败分类

- `missing_parameter` — 参数缺失
- `timeout` — 超时
- `invalid_return_format` — 返回格式错误
- `invalid_retrieval` — 无效检索结果
- `loop_failure` — 多轮循环失败

## 参考项目

- [open-compass/opencompass](https://github.com/open-compass/opencompass) 7.1k★
- [allenai/dolma](https://github.com/allenai/dolma) 1.5k★
- [langchain-ai/langsmith-sdk](https://github.com/langchain-ai/langsmith-sdk) 913★
