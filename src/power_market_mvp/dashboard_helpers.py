from __future__ import annotations

import io
import json
from typing import Any, cast

import altair as alt
import pandas as pd
from pypdf import PdfReader
import streamlit as st
import streamlit.components.v1 as components

from . import load_openai_settings, run_closed_loop
from .llm import build_openai_agent
from .models import MarketScenario
from .scenario import build_custom_scenario, build_sample_scenario


MODEL_OPTIONS = [
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "自定义",
]

CUSTOM_DATA_FIELD_LABELS = {
    "hour": "时段",
    "forecast_load": "预测负荷",
    "expected_dayahead_price": "预期日前电价",
    "actual_load": "实际负荷",
    "actual_dayahead_price": "实际日前电价",
    "realtime_price": "实时电价",
}

CUSTOM_DATA_COLUMN_ALIASES = {
    "hour": ["hour", "hour_index", "时段", "小时"],
    "forecast_load": ["forecast_load", "forecast_load_mwh", "预测负荷", "预测负荷mwh"],
    "expected_dayahead_price": [
        "expected_dayahead_price",
        "expected_dayahead_price_yuan_per_mwh",
        "预期日前电价",
        "预期日前电价元mwh",
    ],
    "actual_load": ["actual_load", "actual_load_mwh", "实际负荷", "实际负荷mwh"],
    "actual_dayahead_price": [
        "actual_dayahead_price",
        "actual_dayahead_price_yuan_per_mwh",
        "实际日前电价",
        "实际日前电价元mwh",
    ],
    "realtime_price": [
        "realtime_price",
        "realtime_price_yuan_per_mwh",
        "实时电价",
        "实时电价元mwh",
    ],
}


RISK_LABELS = {
    "conservative": "稳健",
    "balanced": "平衡",
    "aggressive": "进取",
}

SCENARIO_NOTES = {
    "stable": "负荷与价格波动较小。",
    "peak": "晚高峰更尖锐，移峰收益更明显。",
    "volatile": "价格与负荷波动更大。",
}

SERIES_LABELS = {
    "forecast_load_mwh": "预测负荷",
    "actual_load_mwh": "实际负荷",
    "strategy_bid_mwh": "策略申报",
    "realized_actual_load_mwh": "执行后实际负荷",
    "expected_dayahead_price_yuan_per_mwh": "预期日前电价",
    "dayahead_price_yuan_per_mwh": "成交日前电价",
    "actual_dayahead_price_yuan_per_mwh": "实际日前电价",
    "realtime_price_yuan_per_mwh": "实时电价",
}

PALETTE = {
    "ink": "#183033",
    "muted": "#5c6b66",
    "surface": "#fffaf2",
    "line": "#d9cbb9",
    "gold": "#c97f2c",
    "teal": "#2f7c72",
    "slate": "#5f7480",
    "green": "#3f7d4d",
    "red": "#b45d4f",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-top: #f6ede2;
            --bg-bottom: #edf4ef;
            --surface: #fffaf2;
            --surface-strong: rgba(255, 250, 242, 0.95);
            --line: #d9cbb9;
            --ink: #183033;
            --muted: #5c6b66;
            --gold: #c97f2c;
            --teal: #2f7c72;
            --green: #3f7d4d;
            --red: #b45d4f;
            --shadow: 0 18px 40px rgba(24, 48, 51, 0.08);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(201, 127, 44, 0.10), transparent 28%),
                radial-gradient(circle at top right, rgba(47, 124, 114, 0.11), transparent 30%),
                linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
            color: var(--ink);
            font-family: "Avenir Next", "Segoe UI", sans-serif;
        }

        #MainMenu,
        footer,
        div[data-testid="stDecoration"] {
            display: none !important;
        }

        div[data-testid="stMainMenu"],
        div[data-testid="stAppDeployButton"],
        div[data-testid="stStatusWidget"],
        div[data-testid="stToolbarActions"] {
            display: none !important;
        }

        header[data-testid="stHeader"] {
            background: transparent !important;
            border: none !important;
        }

        [data-testid="stExpandSidebarButton"] {
            position: fixed !important;
            top: 0.9rem;
            left: 0.9rem;
            z-index: 1002 !important;
            display: flex !important;
            align-items: center;
            justify-content: center;
            padding: 0.28rem !important;
            border-radius: 999px;
            background: rgba(255, 250, 242, 0.96);
            border: 1px solid rgba(217, 203, 185, 0.92);
            box-shadow: 0 10px 28px rgba(24, 48, 51, 0.12);
        }

        [data-testid="stExpandSidebarButton"] button {
            color: var(--ink) !important;
        }

        .block-container {
            max-width: 1220px;
            padding-top: 1.2rem;
            padding-bottom: 2.8rem;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(255, 247, 236, 0.97), rgba(238, 246, 241, 0.92));
            border-right: 1px solid rgba(217, 203, 185, 0.9);
        }

        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {
            color: var(--ink) !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 250, 242, 0.9);
            border: 1px solid rgba(217, 203, 185, 0.88);
            border-radius: 999px;
            color: var(--ink) !important;
            padding: 0.55rem 1rem;
        }

        .stTabs [data-baseweb="tab"] p,
        .stTabs [data-baseweb="tab"] span {
            color: var(--ink) !important;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, rgba(24, 48, 51, 0.96), rgba(47, 124, 114, 0.92));
            border-color: rgba(24, 48, 51, 0.9);
        }

        .stTabs [aria-selected="true"] p,
        .stTabs [aria-selected="true"] span {
            color: #f8f5ef !important;
        }

        .stRadio label,
        .stSelectSlider label,
        .stSlider label,
        .stSubheader,
        .stMarkdown p,
        .stCaption,
        .stText {
            color: var(--ink);
        }

        div[data-baseweb="radio"] label,
        div[data-baseweb="radio"] label *,
        div[data-baseweb="slider"] *,
        div[data-testid="stTickBar"] *,
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li {
            color: var(--ink) !important;
        }

        div[data-testid="stDataFrame"] * {
            color: var(--ink);
        }

        .hero-panel {
            background: linear-gradient(135deg, rgba(24, 48, 51, 0.96), rgba(47, 124, 114, 0.92));
            color: #f8f5ef;
            border-radius: 28px;
            padding: 1.8rem 1.8rem 1.6rem 1.8rem;
            box-shadow: var(--shadow);
            border: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 1rem;
        }

        .hero-kicker {
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.72rem;
            color: rgba(248, 245, 239, 0.75);
            margin-bottom: 0.7rem;
        }

        .hero-title {
            font-size: 2.25rem;
            line-height: 1.1;
            font-weight: 700;
            margin-bottom: 0.7rem;
        }

        .hero-copy {
            font-size: 1rem;
            line-height: 1.65;
            color: rgba(248, 245, 239, 0.88);
            max-width: 880px;
            margin-bottom: 1rem;
        }

        .hero-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
        }

        .hero-tag {
            border-radius: 999px;
            padding: 0.38rem 0.72rem;
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.16);
            font-size: 0.82rem;
        }

        .metric-card {
            background: var(--surface-strong);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            border: 1px solid rgba(217, 203, 185, 0.88);
            box-shadow: var(--shadow);
            min-height: 138px;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.88rem;
            margin-bottom: 0.45rem;
        }

        .metric-value {
            color: var(--ink);
            font-size: 1.75rem;
            font-weight: 700;
            line-height: 1.05;
            margin-bottom: 0.5rem;
        }

        .metric-note {
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .agent-card {
            background: rgba(255, 250, 242, 0.9);
            border-radius: 22px;
            border: 1px solid rgba(217, 203, 185, 0.88);
            box-shadow: var(--shadow);
            padding: 1.05rem 1.1rem 0.9rem 1.1rem;
            min-height: 230px;
            margin-bottom: 1rem;
        }

        .agent-head {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin-bottom: 0.8rem;
        }

        .agent-badge {
            width: 0.82rem;
            height: 0.82rem;
            border-radius: 999px;
            display: inline-block;
        }

        .agent-name {
            font-weight: 700;
            color: var(--ink);
            font-size: 1rem;
        }

        .agent-role {
            color: var(--muted);
            font-size: 0.86rem;
            margin-bottom: 0.7rem;
        }

        .agent-list {
            margin: 0;
            padding-left: 1.05rem;
            color: var(--ink);
            line-height: 1.55;
            font-size: 0.93rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_sidebar_reopen_control() -> None:
    components.html("<div></div>", height=0, width=0)


def render_metric_card(title: str, value: str, note: str) -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-note">{note}</div>
    </div>
    """


def render_agent_card(title: str, role: str, items: list[str], color: str) -> str:
    bullet_list = "".join(f"<li>{item}</li>" for item in items)
    return f"""
    <div class="agent-card">
        <div class="agent-head">
            <span class="agent-badge" style="background:{color};"></span>
            <div class="agent-name">{title}</div>
        </div>
        <div class="agent-role">{role}</div>
        <ul class="agent-list">{bullet_list}</ul>
    </div>
    """


def format_hours(hours: list[int]) -> str:
    return " / ".join(f"{hour:02d}:00" for hour in hours)


def build_multi_line_chart(
    df: pd.DataFrame,
    value_columns: list[str],
    title: str,
    value_title: str,
    colors: list[str],
) -> alt.Chart:
    chart_df = df[["hour", *value_columns]].melt(
        id_vars=["hour"],
        value_vars=value_columns,
        var_name="series",
        value_name="value",
    )
    chart_df["series"] = chart_df["series"].replace(SERIES_LABELS)

    return (
        alt.Chart(chart_df)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("hour:O", title="时段"),
            y=alt.Y("value:Q", title=value_title),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(domain=list(chart_df["series"].unique()), range=colors),
                title=None,
            ),
            tooltip=["hour:N", "series:N", alt.Tooltip("value:Q", format=".2f")],
        )
        .properties(height=320, title=title)
        .configure_axis(labelColor=PALETTE["muted"], titleColor=PALETTE["ink"])
        .configure_title(color=PALETTE["ink"], fontSize=18, anchor="start")
        .configure_view(stroke=None)
    )


def build_shift_chart(df: pd.DataFrame) -> alt.Chart:
    shift_df = df[["hour", "planned_shift_mwh"]].copy()
    shift_values = shift_df["planned_shift_mwh"].tolist()
    shift_df["direction"] = [
        "移入谷段" if value >= 0 else "削减峰段" for value in shift_values
    ]

    return (
        alt.Chart(shift_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("hour:O", title="时段"),
            y=alt.Y("planned_shift_mwh:Q", title="计划移峰电量 (MWh)"),
            color=alt.Color(
                "direction:N",
                scale=alt.Scale(
                    domain=["移入谷段", "削减峰段"],
                    range=[PALETTE["teal"], PALETTE["gold"]],
                ),
                title=None,
            ),
            tooltip=["hour:N", alt.Tooltip("planned_shift_mwh:Q", format=".2f")],
        )
        .properties(height=260, title="移峰计划分布")
        .configure_axis(labelColor=PALETTE["muted"], titleColor=PALETTE["ink"])
        .configure_title(color=PALETTE["ink"], fontSize=18, anchor="start")
        .configure_view(stroke=None)
    )


def build_hourly_savings_chart(df: pd.DataFrame) -> alt.Chart:
    savings_df = df[["hour", "hourly_savings_yuan"]].copy()
    savings_values = savings_df["hourly_savings_yuan"].tolist()
    savings_df["signal"] = [
        "节省" if value >= 0 else "增加" for value in savings_values
    ]

    return (
        alt.Chart(savings_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("hour:O", title="时段"),
            y=alt.Y("hourly_savings_yuan:Q", title="相对基线收益 (元)"),
            color=alt.Color(
                "signal:N",
                scale=alt.Scale(
                    domain=["节省", "增加"],
                    range=[PALETTE["green"], PALETTE["red"]],
                ),
                title=None,
            ),
            tooltip=["hour:N", alt.Tooltip("hourly_savings_yuan:Q", format=".2f")],
        )
        .properties(height=300, title="小时级收益变化")
        .configure_axis(labelColor=PALETTE["muted"], titleColor=PALETTE["ink"])
        .configure_title(color=PALETTE["ink"], fontSize=18, anchor="start")
        .configure_view(stroke=None)
    )


def build_cost_breakdown_chart(result: dict) -> alt.Chart:
    breakdown_df = pd.DataFrame(
        [
            {
                "cost_type": "日前成本",
                "baseline": result["baseline"]["dayahead_cost_yuan"],
                "strategy": result["strategy"]["dayahead_cost_yuan"],
            },
            {
                "cost_type": "实时补购",
                "baseline": result["baseline"]["realtime_cost_yuan"],
                "strategy": result["strategy"]["realtime_cost_yuan"],
            },
            {
                "cost_type": "返还收入",
                "baseline": result["baseline"]["surplus_credit_yuan"],
                "strategy": result["strategy"]["surplus_credit_yuan"],
            },
            {
                "cost_type": "偏差罚金",
                "baseline": result["baseline"]["penalty_cost_yuan"],
                "strategy": result["strategy"]["penalty_cost_yuan"],
            },
        ]
    ).melt(id_vars=["cost_type"], var_name="strategy_type", value_name="amount")

    breakdown_df["strategy_type"] = breakdown_df["strategy_type"].replace(
        {"baseline": "基线", "strategy": "策略"}
    )

    return (
        alt.Chart(breakdown_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("cost_type:N", title="成本项"),
            y=alt.Y("amount:Q", title="金额 (元)"),
            xOffset="strategy_type:N",
            color=alt.Color(
                "strategy_type:N",
                scale=alt.Scale(
                    domain=["基线", "策略"], range=[PALETTE["slate"], PALETTE["teal"]]
                ),
                title=None,
            ),
            tooltip=[
                "cost_type:N",
                "strategy_type:N",
                alt.Tooltip("amount:Q", format=".2f"),
            ],
        )
        .properties(height=300, title="成本结构对比")
        .configure_axis(labelColor=PALETTE["muted"], titleColor=PALETTE["ink"])
        .configure_title(color=PALETTE["ink"], fontSize=18, anchor="start")
        .configure_view(stroke=None)
    )


def compute_result(
    risk_preference: str,
    scenario_profile: str,
    deviation_penalty: int,
    max_shift_ratio: int,
    response_ratio: int,
    surplus_credit_discount: int,
    llm_enabled: bool,
    llm_model: str,
    llm_base_url: str,
    _llm_api_key: str,
    custom_scenario: MarketScenario | None = None,
) -> dict:
    return run_closed_loop(
        risk_preference=risk_preference,
        scenario_profile=scenario_profile,
        custom_scenario=custom_scenario,
        rule_overrides={
            "deviation_penalty_yuan_per_mwh": float(deviation_penalty),
            "max_shift_ratio": max_shift_ratio / 100.0,
            "response_ratio": response_ratio / 100.0,
            "surplus_credit_discount": surplus_credit_discount / 100.0,
        },
        llm_enabled=llm_enabled,
        llm_model=llm_model,
        llm_api_key=_llm_api_key or None,
        llm_base_url=llm_base_url or None,
    )


def current_openai_settings():
    return load_openai_settings("gpt-5-mini")


def build_custom_input_template() -> pd.DataFrame:
    return build_input_overview_dataframe(
        build_sample_scenario(profile="stable")
    ).rename(
        columns={
            "forecast_load_mwh": "forecast_load",
            "actual_load_mwh": "actual_load",
            "expected_dayahead_price_yuan_per_mwh": "expected_dayahead_price",
            "actual_dayahead_price_yuan_per_mwh": "actual_dayahead_price",
            "realtime_price_yuan_per_mwh": "realtime_price",
        }
    )


def build_custom_input_template_csv() -> bytes:
    buffer = io.StringIO()
    build_custom_input_template().to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def build_input_overview_dataframe(scenario: MarketScenario) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hour": [f"{hour:02d}:00" for hour in range(24)],
            "forecast_load_mwh": scenario.forecast_load,
            "actual_load_mwh": scenario.actual_load,
            "expected_dayahead_price_yuan_per_mwh": scenario.expected_dayahead_price,
            "actual_dayahead_price_yuan_per_mwh": scenario.actual_dayahead_price,
            "realtime_price_yuan_per_mwh": scenario.realtime_price,
        }
    )


def build_preview_scenario(profile: str) -> MarketScenario:
    return build_sample_scenario(profile=profile)


def build_custom_scenario_from_uploaded_file(
    uploaded_file: Any,
    llm_enabled: bool,
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str,
) -> tuple[MarketScenario, pd.DataFrame, str]:
    file_name = getattr(uploaded_file, "name", "uploaded_file")
    suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    file_bytes = uploaded_file.getvalue()

    if suffix == "csv":
        dataframe = pd.read_csv(io.BytesIO(file_bytes))
        scenario, normalized = build_custom_scenario_from_dataframe(dataframe)
        return scenario, normalized, "csv"

    if suffix == "json":
        payload = json.loads(file_bytes.decode("utf-8", errors="ignore"))
        dataframe = _json_payload_to_dataframe(payload)
        scenario, normalized = build_custom_scenario_from_dataframe(dataframe)
        return scenario, normalized, "json"

    if suffix in {"txt", "md"}:
        text = file_bytes.decode("utf-8", errors="ignore")
        return build_custom_scenario_from_text(
            text,
            llm_enabled=llm_enabled,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            source_label=suffix or "text",
        )

    if suffix == "pdf":
        text = _extract_text_from_pdf(file_bytes)
        return build_custom_scenario_from_text(
            text,
            llm_enabled=llm_enabled,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            source_label="pdf",
        )

    raise ValueError("暂不支持该文件类型，请上传 CSV、JSON、TXT、MD 或 PDF 文件。")


def build_custom_scenario_from_text(
    text: str,
    llm_enabled: bool,
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str,
    source_label: str,
) -> tuple[MarketScenario, pd.DataFrame, str]:
    extracted_dataframe = extract_market_dataframe_with_llm(
        text,
        llm_enabled=llm_enabled,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
    )
    scenario, normalized = build_custom_scenario_from_dataframe(extracted_dataframe)
    return scenario, normalized, f"{source_label}+llm"


def extract_market_dataframe_with_llm(
    text: str,
    llm_enabled: bool,
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str,
) -> pd.DataFrame:
    if not text.strip():
        raise ValueError("文本内容为空，无法提取市场数据。")

    llm_agent = build_openai_agent(
        llm_enabled,
        llm_model,
        llm_api_key=llm_api_key or None,
        llm_base_url=llm_base_url or None,
    )
    if llm_agent is None:
        raise ValueError("解析文本或 PDF 需要启用大模型，并提供可用的 API Key。")

    system_prompt = (
        "你是电力现货市场数据提取助手。"
        "请从文本中提取 24 小时市场数据，并返回 JSON。"
        '返回格式必须是 {"rows": [...]}。'
        "rows 中必须恰好有 24 个对象，每个对象都包含 hour, forecast_load, expected_dayahead_price, actual_load, actual_dayahead_price, realtime_price。"
        "hour 统一输出为 00:00 到 23:00。"
        "所有数值字段必须是数字，不能带单位。"
    )
    user_prompt = (
        "请从下面的文件内容中提取逐小时市场数据。"
        "如果文本中是表格、列表或自然语言描述，请整理成 24 小时结构化数据。"
        "如果原文缺少个别字段，不要臆造；仅在能从上下文明确推断时补全。\n\n"
        f"文件内容：\n{text[:20000]}"
    )
    payload, error = llm_agent.ask_json(system_prompt, user_prompt)
    if payload is None:
        raise ValueError(f"大模型提取失败：{error or '未知错误'}")

    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("大模型返回结果缺少 rows 列表，无法提取数据。")

    return pd.DataFrame(rows)


def build_custom_scenario_from_dataframe(
    dataframe: pd.DataFrame,
) -> tuple[MarketScenario, pd.DataFrame]:
    normalized = normalize_custom_market_dataframe(dataframe)
    scenario = build_custom_scenario(
        forecast_load=normalized["forecast_load"].astype(float).tolist(),
        expected_dayahead_price=normalized["expected_dayahead_price"]
        .astype(float)
        .tolist(),
        actual_load=normalized["actual_load"].astype(float).tolist(),
        actual_dayahead_price=normalized["actual_dayahead_price"]
        .astype(float)
        .tolist(),
        realtime_price=normalized["realtime_price"].astype(float).tolist(),
    )
    return scenario, normalized


def normalize_custom_market_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        raise ValueError("上传的数据为空，请提供 24 个小时的市场数据。")

    column_lookup = {
        _normalize_column_name(column): column for column in dataframe.columns
    }
    rename_map: dict[str, str] = {}

    for target_column, aliases in CUSTOM_DATA_COLUMN_ALIASES.items():
        matched_column = None
        for alias in aliases:
            normalized_alias = _normalize_column_name(alias)
            if normalized_alias in column_lookup:
                matched_column = column_lookup[normalized_alias]
                break
        if matched_column is None:
            raise ValueError(f"缺少必需列：{CUSTOM_DATA_FIELD_LABELS[target_column]}。")
        rename_map[matched_column] = target_column

    selected_columns = list(CUSTOM_DATA_COLUMN_ALIASES.keys())
    normalized = pd.DataFrame(
        dataframe.rename(columns=rename_map)[selected_columns].copy()
    )
    hour_index_values = [
        _parse_hour_index(value) for value in normalized["hour"].tolist()
    ]
    normalized["hour_index"] = hour_index_values

    if any(value is None for value in hour_index_values):
        raise ValueError("时段列格式无法识别，请使用 0-23 或 00:00 这种格式。")

    normalized = pd.DataFrame(
        normalized.sort_values(by=["hour_index"]).reset_index(drop=True)
    )
    hour_values = [int(value) for value in normalized["hour_index"].tolist()]
    if hour_values != list(range(24)):
        raise ValueError("自定义数据必须覆盖 00:00 到 23:00 共 24 个时段，且不能重复。")

    numeric_columns = [
        "forecast_load",
        "expected_dayahead_price",
        "actual_load",
        "actual_dayahead_price",
        "realtime_price",
    ]
    for column in numeric_columns:
        numeric_series = pd.Series(pd.to_numeric(normalized[column], errors="coerce"))
        normalized[column] = numeric_series
        if int(numeric_series.isna().sum()) > 0:
            raise ValueError(
                f"列 {CUSTOM_DATA_FIELD_LABELS[column]} 中存在无法识别的数字。"
            )

    normalized["hour"] = [f"{hour:02d}:00" for hour in hour_values]
    return pd.DataFrame(
        normalized[
            [
                "hour_index",
                "hour",
                "forecast_load",
                "expected_dayahead_price",
                "actual_load",
                "actual_dayahead_price",
                "realtime_price",
            ]
        ].copy()
    )


def _json_payload_to_dataframe(payload: Any) -> pd.DataFrame:
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        if "rows" in payload and isinstance(payload["rows"], list):
            return pd.DataFrame(payload["rows"])
        return pd.DataFrame(payload)
    raise ValueError("JSON 文件格式无法识别，请使用对象数组或包含 rows 的 JSON。")


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError("PDF 中没有可提取的文本内容。")
    return text


def _normalize_column_name(value: object) -> str:
    text = str(value).strip().lower()
    for token in [" ", "-", "_", "(", ")", "（", "）", "/"]:
        text = text.replace(token, "")
    return text


def _parse_hour_index(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None

    if text.endswith(":00"):
        text = text[:-3]

    try:
        hour = int(float(text))
    except ValueError:
        return None

    if 0 <= hour <= 23:
        return float(hour)
    return None
