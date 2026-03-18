from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from . import load_openai_settings, run_closed_loop


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
    "strategy_bid_mwh": "策略申报",
    "realized_actual_load_mwh": "执行后实际负荷",
    "expected_dayahead_price_yuan_per_mwh": "预期日前电价",
    "dayahead_price_yuan_per_mwh": "成交日前电价",
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
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        header[data-testid="stHeader"] {
            display: none !important;
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


@st.cache_data(show_spinner=False, ttl=900)
def compute_result(
    risk_preference: str,
    scenario_profile: str,
    deviation_penalty: int,
    max_shift_ratio: int,
    response_ratio: int,
    surplus_credit_discount: int,
    llm_enabled: bool,
    llm_model: str,
) -> dict:
    return run_closed_loop(
        risk_preference=risk_preference,
        scenario_profile=scenario_profile,
        rule_overrides={
            "deviation_penalty_yuan_per_mwh": float(deviation_penalty),
            "max_shift_ratio": max_shift_ratio / 100.0,
            "response_ratio": response_ratio / 100.0,
            "surplus_credit_discount": surplus_credit_discount / 100.0,
        },
        llm_enabled=llm_enabled,
        llm_model=llm_model,
    )


def current_openai_settings() -> tuple[bool, str]:
    settings = load_openai_settings("gpt-5-mini")
    return bool(settings.api_key), settings.model
