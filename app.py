import hashlib

import pandas as pd
import streamlit as st

from src.power_market_mvp import available_scenario_options
from src.power_market_mvp.dashboard_helpers import (
    MODEL_OPTIONS,
    PALETTE,
    RISK_LABELS,
    SCENARIO_NOTES,
    build_custom_input_template_csv,
    build_custom_scenario_from_uploaded_file,
    build_input_overview_dataframe,
    build_preview_scenario,
    build_cost_breakdown_chart,
    build_hourly_savings_chart,
    build_multi_line_chart,
    build_shift_chart,
    compute_result,
    current_openai_settings,
    format_hours,
    inject_styles,
    inject_sidebar_reopen_control,
    render_agent_card,
    render_metric_card,
)


st.set_page_config(page_title="Power Market MVP", layout="wide")
inject_styles()
inject_sidebar_reopen_control()

scenario_options = available_scenario_options()
default_llm_settings = current_openai_settings()
default_llm_model = default_llm_settings.model or "gpt-5-mini"
default_llm_base_url = default_llm_settings.base_url or ""
default_llm_available = bool(default_llm_settings.api_key)

if default_llm_model in MODEL_OPTIONS:
    default_model_choice = default_llm_model
    default_custom_model = ""
else:
    default_model_choice = "自定义"
    default_custom_model = default_llm_model

st.markdown("## 数据输入方式")
data_mode = st.radio(
    "进入系统后先选择数据来源",
    options=["模拟数据测试", "自定义数据输入"],
    horizontal=True,
    label_visibility="collapsed",
)
if data_mode == "模拟数据测试":
    st.caption("使用系统内置的样例市场数据，适合快速演示完整流程。")
else:
    st.caption("先上传你的文件并生成数据概览，确认无误后再开始策略分析。")

scenario_profile = "stable"
custom_data_error = ""
uploaded_file = None

with st.sidebar:
    st.markdown("## 展示控制台")
    if data_mode == "模拟数据测试":
        scenario_profile = st.radio(
            "场景预设",
            options=list(scenario_options.keys()),
            format_func=lambda key: scenario_options.get(str(key), ""),
        )
        st.caption(SCENARIO_NOTES[scenario_profile])
    else:
        st.markdown("### 数据模式")
        st.caption("当前为自定义数据输入模式，系统不会使用内置模拟场景。")

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
    llm_enabled = st.toggle("启用大模型", value=True)
    st.write("OpenAI / 兼容 OpenAI 接口")
    model_choice = st.selectbox(
        "模型", MODEL_OPTIONS, index=MODEL_OPTIONS.index(default_model_choice)
    )
    custom_model = st.text_input(
        "自定义模型名",
        value=default_custom_model,
        placeholder="例如 gpt-5-mini 或其他兼容模型",
        disabled=model_choice != "自定义",
    )
    llm_model = custom_model.strip() if model_choice == "自定义" else model_choice
    if not llm_model:
        llm_model = "gpt-5-mini"

    llm_api_key = st.text_input(
        "API Key",
        value="",
        type="password",
        placeholder="留空则尝试使用服务器默认配置",
        help="仅当前页面会话使用，不会写入仓库。",
    )
    llm_base_url = st.text_input(
        "Base URL",
        value=default_llm_base_url,
        placeholder="https://api.openai.com/v1",
        help="兼容 OpenAI 协议的服务可在这里填写自定义地址。",
    )

    using_page_api = bool(llm_api_key.strip())
    llm_ready = using_page_api or default_llm_available
    if using_page_api:
        st.caption(f"当前来源：页面输入 · 模型 {llm_model}")
    elif default_llm_available:
        st.caption(f"当前来源：服务器默认配置 · 模型 {default_llm_model}")
    else:
        st.caption("当前未检测到可用 API Key，请在页面中输入。")

if data_mode == "自定义数据输入":
    st.subheader("上传自定义数据")
    st.write(
        "支持上传 CSV、JSON、TXT、MD、PDF 文件。结构化文件会直接读取，文本和 PDF 会交给大模型自动提取 24 小时市场数据。"
    )
    st.download_button(
        "下载 CSV 模板",
        data=build_custom_input_template_csv(),
        file_name="market_input_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    uploaded_file = st.file_uploader(
        "上传市场数据文件",
        type=["csv", "json", "txt", "md", "pdf"],
        help="CSV/JSON 可直接读取；TXT/MD/PDF 会交给大模型抽取数据。",
    )
    if uploaded_file is None:
        st.info("还没有上传数据；如果只是想体验系统，可以切换到“模拟数据测试”。")

file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest() if uploaded_file else ""

preview_signature = {
    "data_mode": data_mode,
    "scenario_profile": scenario_profile if data_mode == "模拟数据测试" else "custom",
    "file_hash": file_hash,
    "llm_enabled": llm_enabled and llm_ready,
    "llm_model": llm_model,
    "llm_base_url": llm_base_url,
}

analysis_signature = {
    **preview_signature,
    "risk_preference": risk_preference,
    "deviation_penalty": deviation_penalty,
    "max_shift_ratio": max_shift_ratio,
    "response_ratio": response_ratio,
    "surplus_credit_discount": surplus_credit_discount,
}

preview_col, analysis_col = st.columns(2)
preview_clicked = preview_col.button(
    "生成数据分析可视化",
    use_container_width=True,
)
preview_ready = (
    st.session_state.get("data_preview_signature") == preview_signature
    and st.session_state.get("data_preview_scenario") is not None
)
analysis_clicked = analysis_col.button(
    "开始策略分析",
    type="primary",
    use_container_width=True,
    disabled=not preview_ready,
)

if preview_clicked:
    if data_mode == "模拟数据测试":
        preview_scenario = build_preview_scenario(scenario_profile)
        preview_df = build_input_overview_dataframe(preview_scenario)
        st.session_state["data_preview_scenario"] = preview_scenario
        st.session_state["data_preview_df"] = preview_df
        st.session_state["data_preview_source"] = "simulation"
        st.session_state["data_preview_signature"] = preview_signature
        st.session_state.pop("analysis_result", None)
        st.session_state.pop("analysis_signature", None)
    else:
        if uploaded_file is None:
            st.error("请先上传文件，再生成数据概览。")
        else:
            try:
                preview_spinner = (
                    f"正在用 {llm_model} 解析文件并生成数据概览，请稍候..."
                    if uploaded_file.name.lower().endswith((".txt", ".md", ".pdf"))
                    else "正在校验并生成数据概览，请稍候..."
                )
                with st.spinner(preview_spinner):
                    preview_scenario, preview_df, preview_source = (
                        build_custom_scenario_from_uploaded_file(
                            uploaded_file,
                            llm_enabled=llm_enabled and llm_ready,
                            llm_model=llm_model,
                            llm_api_key=llm_api_key,
                            llm_base_url=llm_base_url,
                        )
                    )
                st.session_state["data_preview_scenario"] = preview_scenario
                st.session_state["data_preview_df"] = preview_df
                st.session_state["data_preview_source"] = preview_source
                st.session_state["data_preview_signature"] = preview_signature
                st.session_state.pop("analysis_result", None)
                st.session_state.pop("analysis_signature", None)
            except Exception as exc:
                custom_data_error = str(exc)
                st.error(custom_data_error)

stored_preview_scenario = st.session_state.get("data_preview_scenario")
stored_preview_df = st.session_state.get("data_preview_df")
stored_preview_source = st.session_state.get("data_preview_source", "")
stored_preview_signature = st.session_state.get("data_preview_signature")
preview_exists = stored_preview_scenario is not None and stored_preview_df is not None
preview_ready = preview_exists and stored_preview_signature == preview_signature

if analysis_clicked:
    if not preview_ready or stored_preview_scenario is None:
        st.error("请先点击“生成数据分析可视化”，确认输入数据后再开始策略分析。")
    else:
        spinner_text = (
            f"正在调用 {llm_model} 进行多智能体分析，请稍候..."
            if llm_enabled and llm_ready
            else "正在生成本地策略结果，请稍候..."
        )
        with st.spinner(spinner_text):
            result = compute_result(
                risk_preference=risk_preference,
                scenario_profile=scenario_profile,
                deviation_penalty=deviation_penalty,
                max_shift_ratio=max_shift_ratio,
                response_ratio=response_ratio,
                surplus_credit_discount=surplus_credit_discount,
                llm_enabled=llm_enabled and llm_ready,
                llm_model=llm_model,
                llm_base_url=llm_base_url,
                _llm_api_key=llm_api_key,
                custom_scenario=stored_preview_scenario,
            )
        st.session_state["analysis_result"] = result
        st.session_state["analysis_signature"] = analysis_signature

stored_result = st.session_state.get("analysis_result")
stored_signature = st.session_state.get("analysis_signature")

if not preview_exists:
    st.info("请先选择数据来源，并点击“生成数据分析可视化”查看输入数据。")
    st.stop()

if not preview_ready:
    st.warning(
        "输入数据或模型配置已变化，当前显示的是上一次生成的数据概览；请重新点击“生成数据分析可视化”。"
    )

preview_df = pd.DataFrame(stored_preview_df)
st.subheader("输入数据概览")
if data_mode == "自定义数据输入":
    st.caption(f"当前数据来源：{stored_preview_source}")
else:
    st.caption(f"当前场景：{scenario_options.get(scenario_profile, scenario_profile)}")

preview_tabs = st.tabs(["负荷概览", "价格概览", "数据明细"])
with preview_tabs[0]:
    st.altair_chart(
        build_multi_line_chart(
            preview_df,
            ["forecast_load_mwh", "actual_load_mwh"],
            "输入负荷数据概览",
            "电量 (MWh)",
            [PALETTE["gold"], PALETTE["teal"]],
        ),
        use_container_width=True,
    )
with preview_tabs[1]:
    st.altair_chart(
        build_multi_line_chart(
            preview_df,
            [
                "expected_dayahead_price_yuan_per_mwh",
                "actual_dayahead_price_yuan_per_mwh",
                "realtime_price_yuan_per_mwh",
            ],
            "输入电价数据概览",
            "价格 (元/MWh)",
            [PALETTE["slate"], PALETTE["gold"], PALETTE["teal"]],
        ),
        use_container_width=True,
    )
with preview_tabs[2]:
    preview_table = preview_df.rename(
        columns={
            "hour": "时段",
            "forecast_load_mwh": "预测负荷(MWh)",
            "actual_load_mwh": "实际负荷(MWh)",
            "expected_dayahead_price_yuan_per_mwh": "预期日前电价(元/MWh)",
            "actual_dayahead_price_yuan_per_mwh": "实际日前电价(元/MWh)",
            "realtime_price_yuan_per_mwh": "实时电价(元/MWh)",
        }
    )
    st.dataframe(preview_table, use_container_width=True, hide_index=True)

if stored_result is None:
    st.info("数据概览已生成；确认无误后，点击“开始策略分析”。")
    st.stop()

if stored_signature != analysis_signature:
    st.warning(
        "你已经修改了参数，当前展示的仍是上一次策略分析结果；点击“开始策略分析”后会刷新。"
    )
    st.stop()

result = stored_result

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
