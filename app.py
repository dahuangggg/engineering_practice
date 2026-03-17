import altair as alt
import pandas as pd
import streamlit as st

from src.power_market_mvp import available_scenario_options, run_closed_loop


st.set_page_config(page_title="Power Market MVP", layout="wide")

RISK_LABELS = {
    "conservative": "稳健",
    "balanced": "平衡",
    "aggressive": "进取",
}

SCENARIO_NOTES = {
    "stable": "负荷与价格波动较小，适合展示基线策略。",
    "peak": "晚高峰更尖锐，适合强调移峰收益。",
    "volatile": "价格起伏更大，适合展示反馈与调优价值。",
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


inject_styles()

scenario_options = available_scenario_options()

with st.sidebar:
    st.markdown("## 展示控制台")
    scenario_profile = st.radio(
        "场景预设",
        options=list(scenario_options.keys()),
        format_func=lambda key: scenario_options.get(str(key), ""),
    )
    st.caption(SCENARIO_NOTES[scenario_profile])

    risk_preference = st.select_slider(
        "风险偏好",
        options=list(RISK_LABELS.keys()),
        value="balanced",
        format_func=lambda key: RISK_LABELS.get(str(key), ""),
    )

    st.markdown("### 规则参数")
    deviation_penalty = st.slider("偏差罚金 (元/MWh)", 0, 50, 18)
    max_shift_ratio = st.slider("最大移峰比例 (%)", 2, 20, 12)
    response_ratio = st.slider("执行兑现率 (%)", 50, 100, 80)
    surplus_credit_discount = st.slider("余量回收折扣 (%)", 50, 100, 88)

result = run_closed_loop(
    risk_preference=risk_preference,
    scenario_profile=scenario_profile,
    rule_overrides={
        "deviation_penalty_yuan_per_mwh": float(deviation_penalty),
        "max_shift_ratio": max_shift_ratio / 100.0,
        "response_ratio": response_ratio / 100.0,
        "surplus_credit_discount": surplus_credit_discount / 100.0,
    },
)

dashboard_df = pd.DataFrame(result["dashboard_rows"])
savings = float(result["feedback"]["savings_vs_baseline_yuan"])
deviation_rate = float(result["feedback"]["strategy_deviation_rate"]) * 100
next_shift_ratio = float(result["optimization"]["recommended_shift_ratio"]) * 100
shifted_energy = float(result["decision"]["shifted_energy_mwh"])
scenario_display_name = result["scenario_display_name"]

st.markdown(
    f"""
    <div class="hero-panel">
        <div class="hero-kicker">工业园区电力现货交易 · 多智能体闭环</div>
        <div class="hero-title">电力现货辅助决策展示台</div>
        <div class="hero-copy">
            当前为 <strong>{scenario_display_name}</strong> 场景，系统自动完成市场感知、申报决策、执行结算、效果反馈与下一轮调优。
            在 <strong>{RISK_LABELS[risk_preference]}</strong> 策略下，相比基线方案节省 <strong>{savings:,.2f} 元</strong>，
            偏差率控制在 <strong>{deviation_rate:.2f}%</strong>，适合作为课程项目演示版的核心看板。
        </div>
        <div class="hero-tags">
            <span class="hero-tag">场景：{scenario_display_name}</span>
            <span class="hero-tag">风险偏好：{RISK_LABELS[risk_preference]}</span>
            <span class="hero-tag">高价时段：{format_hours(result["perception"]["peak_hours"])}</span>
            <span class="hero-tag">低价时段：{format_hours(result["perception"]["valley_hours"])}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_row_one = st.columns(3)
metric_row_one[0].markdown(
    render_metric_card(
        "预测总负荷",
        f"{result['perception']['forecast_total_mwh']:.2f} MWh",
        "汇总次日 24 小时预测负荷，用来确定申报总盘子。",
    ),
    unsafe_allow_html=True,
)
metric_row_one[1].markdown(
    render_metric_card(
        "基线成本",
        f"{result['baseline']['total_cost_yuan']:.2f} 元",
        "不做移峰策略时的全天结算成本。",
    ),
    unsafe_allow_html=True,
)
metric_row_one[2].markdown(
    render_metric_card(
        "策略成本",
        f"{result['strategy']['total_cost_yuan']:.2f} 元",
        "执行移峰申报后的全天结算成本。",
    ),
    unsafe_allow_html=True,
)

metric_row_two = st.columns(3)
metric_row_two[0].markdown(
    render_metric_card(
        "相对收益",
        f"{savings:,.2f} 元",
        "正值表示策略优于基线，适合放在答辩第一页。",
    ),
    unsafe_allow_html=True,
)
metric_row_two[1].markdown(
    render_metric_card(
        "偏差率",
        f"{deviation_rate:.2f}%",
        "衡量申报与执行偏差，越低越稳健。",
    ),
    unsafe_allow_html=True,
)
metric_row_two[2].markdown(
    render_metric_card(
        "下一轮推荐移峰比例",
        f"{next_shift_ratio:.2f}%",
        f"本轮共调整 {shifted_energy:.2f} MWh，用于下一轮参数更新。",
    ),
    unsafe_allow_html=True,
)

st.subheader("智能体闭环")
agent_row_one = st.columns(3)
agent_row_one[0].markdown(
    render_agent_card(
        "感知智能体",
        "读入规则、负荷和价格，形成市场状态特征。",
        [
            result["perception"]["insights"][0],
            result["perception"]["insights"][1],
            f"偏差罚金 {result['perception']['rules']['deviation_penalty_yuan_per_mwh']:.0f} 元/MWh，最大移峰比例 {result['perception']['rules']['max_shift_ratio'] * 100:.1f}%。",
        ],
        PALETTE["gold"],
    ),
    unsafe_allow_html=True,
)
agent_row_one[1].markdown(
    render_agent_card(
        "决策智能体",
        "按风险偏好生成次日电量申报与移峰计划。",
        [
            result["decision"]["strategy_note"],
            f"日总申报电量 {result['decision']['daily_bid_total_mwh']:.2f} MWh。",
            f"谷段承接电量 {result['decision']['shifted_energy_mwh']:.2f} MWh。",
        ],
        PALETTE["teal"],
    ),
    unsafe_allow_html=True,
)
agent_row_one[2].markdown(
    render_agent_card(
        "执行智能体",
        "模拟日前成交、实时偏差和结算结果。",
        [
            f"日前成本 {result['strategy']['dayahead_cost_yuan']:.2f} 元，实时补购 {result['strategy']['realtime_cost_yuan']:.2f} 元。",
            f"余量回收 {result['strategy']['surplus_credit_yuan']:.2f} 元，偏差罚金 {result['strategy']['penalty_cost_yuan']:.2f} 元。",
            f"执行兑现率 {response_ratio}% 下，实际总负荷 {result['strategy']['actual_total_load_mwh']:.2f} MWh。",
        ],
        PALETTE["slate"],
    ),
    unsafe_allow_html=True,
)

agent_row_two = st.columns(2)
agent_row_two[0].markdown(
    render_agent_card(
        "反馈智能体",
        "比较基线与策略效果，输出结构化诊断。",
        [
            result["feedback"]["diagnosis"][0],
            result["feedback"]["diagnosis"][1],
            result["feedback"]["diagnosis"][2],
        ],
        PALETTE["green"],
    ),
    unsafe_allow_html=True,
)
agent_row_two[1].markdown(
    render_agent_card(
        "优化智能体",
        "根据收益和偏差，给出下一轮参数建议。",
        [
            result["optimization"]["recommendation"],
            f"当前移峰比例 {result['optimization']['current_shift_ratio'] * 100:.2f}%，建议调整为 {next_shift_ratio:.2f}%。",
            f"适合继续迭代 {scenario_display_name} 场景下的申报策略。",
        ],
        PALETTE["red"],
    ),
    unsafe_allow_html=True,
)

st.subheader("可视化分析")
chart_tabs = st.tabs(["负荷与申报", "价格走势", "成本收益", "小时明细"])

with chart_tabs[0]:
    st.altair_chart(
        build_multi_line_chart(
            dashboard_df,
            ["forecast_load_mwh", "strategy_bid_mwh", "realized_actual_load_mwh"],
            "预测负荷、策略申报与执行后实际负荷",
            "电量 (MWh)",
            [PALETTE["slate"], PALETTE["gold"], PALETTE["teal"]],
        ),
        use_container_width=True,
    )
    st.altair_chart(build_shift_chart(dashboard_df), use_container_width=True)

with chart_tabs[1]:
    st.altair_chart(
        build_multi_line_chart(
            dashboard_df,
            [
                "expected_dayahead_price_yuan_per_mwh",
                "dayahead_price_yuan_per_mwh",
                "realtime_price_yuan_per_mwh",
            ],
            "预期、日前与实时电价对比",
            "价格 (元/MWh)",
            [PALETTE["slate"], PALETTE["gold"], PALETTE["teal"]],
        ),
        use_container_width=True,
    )

with chart_tabs[2]:
    cost_col, savings_col = st.columns([1, 1])
    cost_col.altair_chart(build_cost_breakdown_chart(result), use_container_width=True)
    savings_col.altair_chart(
        build_hourly_savings_chart(dashboard_df), use_container_width=True
    )

with chart_tabs[3]:
    display_df = dashboard_df[
        [
            "hour",
            "forecast_load_mwh",
            "strategy_bid_mwh",
            "realized_actual_load_mwh",
            "planned_shift_mwh",
            "dayahead_price_yuan_per_mwh",
            "realtime_price_yuan_per_mwh",
            "baseline_hour_cost_yuan",
            "strategy_hour_cost_yuan",
            "hourly_savings_yuan",
        ]
    ].copy()
    display_df.columns = [
        "时段",
        "预测负荷(MWh)",
        "策略申报(MWh)",
        "执行后实际负荷(MWh)",
        "计划移峰(MWh)",
        "日前电价(元/MWh)",
        "实时电价(元/MWh)",
        "基线成本(元)",
        "策略成本(元)",
        "相对收益(元)",
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
