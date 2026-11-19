# engineering-practice · 电力现货辅助决策 MVP

[中文](#中文) | [English](#english)

---

## 中文

基于多智能体协同的电力现货市场辅助决策系统 MVP：模拟工业园区购电申报，跑通“感知 → 决策 → 执行 → 反馈 → 优化”闭环。

### 项目状态

早期项目（课程工程实践原型），不再维护。

### 功能

- 五个智能体闭环：感知、决策、优化智能体可调用 OpenAI 模型；执行智能体用确定性算法模拟日前申报、实时偏差与结算；反馈智能体做收益/偏差复盘
- 未配置 OpenAI API Key 时自动关闭大模型，仅用规则与确定性逻辑运行
- 内置场景：平稳日、尖峰日、波动日；风险偏好：稳健、平衡、进取
- 规则参数可调：偏差罚金、最大移峰比例、执行兑现率、余量回收折扣
- 自定义数据输入：CSV / JSON / TXT / MD / PDF，文本可由大模型抽取 24 小时数据
- Streamlit 看板：负荷曲线、电价走势、成本结构、小时级收益表
- 简化范围：不接真实交易平台，不做真实强化学习训练

### 技术栈

Python 3.12 · Streamlit · OpenAI Python SDK · pandas · Altair · pypdf · uv

### 本地运行

```bash
# 使用 uv（仓库包含 uv.lock）
uv sync
uv run python run_demo.py                 # 命令行演示
uv run streamlit run app.py               # 可视化页面
uv run python -m unittest discover -s tests -v   # 单元测试

# 或使用 pip
pip install -r requirements.txt
python3 run_demo.py
streamlit run app.py
```

可选环境变量（也会从 `~/.zshrc` 的 `export` 行读取）：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（默认 `gpt-5-mini`）。

### 目录结构

```
app.py                     Streamlit 可视化页面
run_demo.py                命令行演示入口
src/power_market_mvp/      核心代码：agents / pipeline / scenario / rules / llm / models / dashboard_helpers
data/market_rules.txt      样例市场规则文本
tests/test_mvp.py          单元测试
workflow_logic.md          页面流程与分析闭环（Mermaid）
页面名词说明.md             页面术语与参数说明
info/                      选题说明与流程图
```

---

## English

An MVP of a multi-agent decision-support system for the electricity spot market: it simulates an industrial park's day-ahead power purchase bidding and runs a closed loop of perception → decision → execution → feedback → optimization.

### Status

Early project (a course engineering-practice prototype), no longer actively maintained.

### Features

- Five-agent closed loop: perception, decision and optimization agents can call an OpenAI model; the execution agent deterministically simulates day-ahead bids, real-time deviations and settlement; the feedback agent reviews profit and deviation
- Runs with the LLM disabled (rules and deterministic logic only) when no OpenAI API key is configured
- Built-in scenarios: stable, peak, volatile; risk preferences: conservative, balanced, aggressive
- Tunable rules: deviation penalty, max load-shift ratio, execution realization rate, surplus credit discount
- Custom data input: CSV / JSON / TXT / MD / PDF; the LLM can extract 24-hour data from text files
- Streamlit dashboard: load curves, price trends, cost breakdown, hourly profit table
- Simplified scope: no real trading platform, no real reinforcement-learning training

### Tech stack

Python 3.12 · Streamlit · OpenAI Python SDK · pandas · Altair · pypdf · uv

### Getting started

```bash
# With uv (uv.lock is included)
uv sync
uv run python run_demo.py                 # CLI demo
uv run streamlit run app.py               # dashboard
uv run python -m unittest discover -s tests -v   # unit tests

# Or with pip
pip install -r requirements.txt
python3 run_demo.py
streamlit run app.py
```

Optional environment variables (also read from `export` lines in `~/.zshrc`): `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (default `gpt-5-mini`).

### Directory structure

```
app.py                     Streamlit dashboard
run_demo.py                CLI demo entry point
src/power_market_mvp/      Core code: agents / pipeline / scenario / rules / llm / models / dashboard_helpers
data/market_rules.txt      Sample market rules text
tests/test_mvp.py          Unit tests
workflow_logic.md          Page flow and analysis loop (Mermaid)
页面名词说明.md             Glossary of dashboard terms and parameters (Chinese)
info/                      Topic description and flow diagram
```
