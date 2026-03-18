import pandas as pd
import streamlit as st

from src.power_market_mvp import available_scenario_options
from src.power_market_mvp.dashboard_helpers import (
    PALETTE,
    RISK_LABELS,
    SCENARIO_NOTES,
    build_cost_breakdown_chart,
    build_hourly_savings_chart,
    build_multi_line_chart,
    build_shift_chart,
    compute_result,
    current_openai_settings,
    format_hours,
    inject_styles,
    render_agent_card,
    render_metric_card,
)


st.set_page_config(page_title="Power Market MVP", layout="wide")
inject_styles()

scenario_options = available_scenario_options()
llm_ready, llm_model = current_openai_settings()

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

    st.markdown("### 大模型")
    st.write("OpenAI")
    st.caption(llm_model if llm_ready else "未检测到 OpenAI 配置")

with st.spinner(f"正在调用 {llm_model} 进行多智能体分析，请稍候..."):
    result = compute_result(
        risk_preference=risk_preference,
        scenario_profile=scenario_profile,
        deviation_penalty=deviation_penalty,
        max_shift_ratio=max_shift_ratio,
        response_ratio=response_ratio,
        surplus_credit_discount=surplus_credit_discount,
        llm_enabled=llm_ready,
        llm_model=llm_model,
    )

dashboard_df = pd.DataFrame(result["dashboard_rows"])
savings = float(result["feedback"]["savings_vs_baseline_yuan"])
deviation_rate = float(result["feedback"]["strategy_deviation_rate"]) * 100
next_shift_ratio = float(result["optimization"]["recommended_shift_ratio"]) * 100
shifted_energy = float(result["decision"]["shifted_energy_mwh"])
scenario_display_name = result["scenario_display_name"]
llm_status = result["llm"]

st.markdown(
    f"""
    <div class="hero-panel">
        <div class="hero-kicker">工业园区电力现货交易 · 多智能体闭环</div>
        <div class="hero-title">电力现货辅助决策展示台</div>
        <div class="hero-copy">
            当前为 <strong>{scenario_display_name}</strong> 场景，系统自动完成市场感知、申报决策、执行结算、效果反馈与下一轮调优。
            在 <strong>{RISK_LABELS[risk_preference]}</strong> 策略下，相比基线方案节省 <strong>{savings:,.2f} 元</strong>，
            偏差率控制在 <strong>{deviation_rate:.2f}%</strong>。当前由 <strong>{llm_status["provider"]}</strong>
            模型 <strong>{llm_status["model"] or "未启用"}</strong> 参与规则理解、策略建议和复盘优化。
        </div>
        <div class="hero-tags">
            <span class="hero-tag">场景：{scenario_display_name}</span>
            <span class="hero-tag">风险偏好：{RISK_LABELS[risk_preference]}</span>
            <span class="hero-tag">大模型：{llm_status["model"] or "未启用"}</span>
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
        "正值表示策略优于基线。",
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
            f"市场判断：{result['perception']['market_regime']}。",
            result["perception"]["llm_summary"] or result["perception"]["insights"][0],
            f"规则解析来源：{result['perception']['rule_parser']}，偏差罚金 {result['perception']['rules']['deviation_penalty_yuan_per_mwh']:.0f} 元/MWh。",
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
            result["decision"]["decision_highlight"],
            result["decision"]["strategy_note"],
            f"决策来源 {result['decision']['decision_source']}，重点转移时段为 {format_hours(result['decision']['focused_peak_hours'])} -> {format_hours(result['decision']['focused_valley_hours'])}。",
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
            result["feedback"]["optimization_brief"],
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
            f"优化来源：{result['optimization']['source']}，适合继续迭代 {scenario_display_name} 场景下的申报策略。",
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
