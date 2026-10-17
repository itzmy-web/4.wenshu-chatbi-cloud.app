# 问数 ChatBI · 自然语言数据查询与分析平台

用大白话问数据：输入「2025 年哪个产品销售额最高」，系统自动完成 **意图识别 → 表/字段匹配 → SQL 生成 → 执行 → 图表呈现 → 结论解读** 全链路，输出可直接汇报的分析结果。

## 在线演示

**在线演示**：<http://39.107.107.246:8082/>

> 演示环境每次打开需先登录（手机号验证码 / 微信扫码 / 支付宝扫码，均为演示仿真）；验证码任意 6 位即可通过。

## 核心能力

| 能力 | 说明 |
|---|---|
| 自然语言问数 | LangGraph 编排的多节点 Text2SQL Agent：schema linking → SQL 生成 → 自检纠错 → 执行 → 空结果回炉 |
| 流式输出 | FastAPI + SSE，思考过程与答案逐字返回 |
| 智能图表 | ECharts 自动选图；数字型月份列（如 202501）兜底转类目轴，避免趋势被画成散点 |
| 数据大屏 | 经营指标一屏总览（`/dashboard.html`） |
| 每日报告 | 定时生成经营日报（`/report.html`），支持订阅推送 |
| 数据管理 | 数据字典、记录、收藏、问法推荐（`/dictionary.html`、`/records.html`、`/favorites.html`） |
| 登录门禁 | 每次打开先见登录页；token 仅驻内存，`?from=sub` 子页跳回才恢复，刷新/重开必须重新登录 |

## 技术栈

- **Agent 编排**：LangGraph（`app/agent/graph.py` + `app/agent/nodes/`，十余个节点含条件路由）
- **Web**：FastAPI + SSE 流式 + 静态前端（`static/`）
- **存储**：云端版 SQLite（内置业务词汇向量 + FTS5 全文检索，零外部依赖）
- **LLM**：OpenAI 兼容协议接入（`OPENAI_API_BASE` / `OPENAI_API_KEY`），未配置 Key 时自动降级为规则 / 演示模式

## 快速开始

```bash
pip install -r requirements.txt        # 或 uv sync
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后访问 `http://127.0.0.1:8000`，登录页任意手机号 + 任意 6 位验证码即可进入演示。

## 说明

- 云端版（本仓库）为「单端口可发布」形态：SQLite + 内置词汇向量 + FTS，无 MySQL / Qdrant / ES 依赖
- 仓库内不包含任何真实密钥；`.env` 已在 `.gitignore` 中排除，仅保留 `.env.example` 占位模板
