from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, cast

from .agents import (
    DecisionAgent,
    ExecutionAgent,
    FeedbackAgent,
    OptimizationAgent,
    PerceptionAgent,
)
from .llm import build_openai_agent
from .models import MarketScenario, MarketState
from .rules import load_rules_text
from .scenario import (
    build_sample_scenario,
    resolve_scenario_profile,
    scenario_display_name,
)
from .utils import format_hours


def build_dashboard_rows(
    state: MarketState,
    decision: dict[str, Any],
    baseline: dict[str, Any],
    strategy: dict[str, Any],
) -> list[dict[str, Any]]:
    planned_shift = cast(list[float], decision["planned_shift"])
    bid_quantities = cast(list[float], decision["bid_quantities"])
    focused_peak_hours = cast(
        list[int], decision.get("focused_peak_hours", state.peak_hours)
    )
    focused_valley_hours = cast(
        list[int], decision.get("focused_valley_hours", state.valley_hours)
    )
    baseline_rows = cast(list[dict[str, Any]], baseline["hourly_rows"])
    strategy_rows = cast(list[dict[str, Any]], strategy["hourly_rows"])

    dashboard_rows: list[dict[str, Any]] = []

    for hour in range(24):
        baseline_row = baseline_rows[hour]
        strategy_row = strategy_rows[hour]
        baseline_hour_cost = float(baseline_row["hour_total_cost_yuan"])
        strategy_hour_cost = float(strategy_row["hour_total_cost_yuan"])

        dashboard_rows.append(
            {
                "hour_index": hour,
                "hour": f"{hour:02d}:00",
                "forecast_load_mwh": round(state.scenario.forecast_load[hour], 2),
                "baseline_bid_mwh": round(state.scenario.forecast_load[hour], 2),
                "strategy_bid_mwh": round(bid_quantities[hour], 2),
                "raw_actual_load_mwh": round(state.scenario.actual_load[hour], 2),
                "realized_actual_load_mwh": float(strategy_row["actual_load_mwh"]),
                "planned_shift_mwh": round(planned_shift[hour], 2),
                "expected_dayahead_price_yuan_per_mwh": round(
                    state.scenario.expected_dayahead_price[hour], 2
                ),
                "dayahead_price_yuan_per_mwh": float(
                    strategy_row["dayahead_price_yuan_per_mwh"]
                ),
                "realtime_price_yuan_per_mwh": float(
                    strategy_row["realtime_price_yuan_per_mwh"]
                ),
                "baseline_hour_cost_yuan": baseline_hour_cost,
                "strategy_hour_cost_yuan": strategy_hour_cost,
                "hourly_savings_yuan": round(
                    baseline_hour_cost - strategy_hour_cost, 2
                ),
                "is_peak_hour": hour in focused_peak_hours,
                "is_valley_hour": hour in focused_valley_hours,
            }
        )

    return dashboard_rows


def run_closed_loop(
    risk_preference: str = "balanced",
    rules_path: str | Path | None = None,
    scenario_profile: str = "stable",
    custom_scenario: MarketScenario | None = None,
    rule_overrides: dict[str, float] | None = None,
    llm_enabled: bool = False,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
    llm_base_url: str | None = None,
) -> dict[str, Any]:
    if custom_scenario is not None:
        scenario_key = "custom"
        scenario = custom_scenario
        current_scenario_display_name = scenario_display_name(scenario_key)
    else:
        scenario_key, scenario_config = resolve_scenario_profile(scenario_profile)
        scenario = build_sample_scenario(profile=scenario_key)
        current_scenario_display_name = str(scenario_config["display_name"])
    rules_text = load_rules_text(rules_path)
    llm_agent = build_openai_agent(
        llm_enabled,
        llm_model,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
    )

    perception_agent = PerceptionAgent()
    decision_agent = DecisionAgent()
    execution_agent = ExecutionAgent()
    feedback_agent = FeedbackAgent()
    optimization_agent = OptimizationAgent()

    state = perception_agent.analyze(
        scenario,
        rules_text,
        risk_preference,
        rule_overrides=rule_overrides,
        llm_agent=llm_agent,
        scenario_profile=scenario_key,
    )
    decision = decision_agent.plan(state, llm_agent=llm_agent)
    planned_shift = cast(list[float], decision["planned_shift"])

    baseline = execution_agent.simulate(state, [0.0] * 24, label="baseline")
    strategy = execution_agent.simulate(state, planned_shift, label="strategy")
    feedback = feedback_agent.review(
        state,
        decision,
        baseline,
        strategy,
        llm_agent=llm_agent,
    )
    optimization = optimization_agent.tune(state, feedback)
    baseline_hourly_rows = cast(list[dict[str, Any]], baseline["hourly_rows"])
    hourly_rows = cast(list[dict[str, Any]], strategy["hourly_rows"])
    dashboard_rows = build_dashboard_rows(state, decision, baseline, strategy)
    llm_status = llm_agent is not None

    return {
        "scenario_profile": scenario_key,
        "scenario_display_name": current_scenario_display_name,
        "llm": {
            "enabled": llm_status,
            "provider": "OpenAI" if llm_status else "disabled",
            "model": llm_agent.model if llm_status else None,
            "rule_parser": state.rule_parser,
            "market_regime": state.market_regime,
            "perception_summary": state.llm_summary or state.insights[0],
            "decision_summary": decision.get(
                "decision_highlight", decision["strategy_note"]
            ),
            "feedback_summary": feedback["diagnosis"][0],
            "optimization_summary": optimization["recommendation"],
        },
        "perception": {
            "forecast_total_mwh": round(sum(state.scenario.forecast_load), 2),
            "average_expected_price_yuan_per_mwh": round(
                statistics.fmean(state.scenario.expected_dayahead_price),
                2,
            ),
            "risk_preference": state.risk_preference,
            "market_regime": state.market_regime,
            "llm_summary": state.llm_summary,
            "rule_parser": state.rule_parser,
            "peak_hours": state.peak_hours,
            "valley_hours": state.valley_hours,
            "insights": state.insights,
            "rules": {
                "deviation_penalty_yuan_per_mwh": state.rules.deviation_penalty_yuan_per_mwh,
                "surplus_credit_discount": state.rules.surplus_credit_discount,
                "max_shift_ratio": state.rules.max_shift_ratio,
                "response_ratio": state.rules.response_ratio,
            },
        },
        "decision": decision,
        "baseline": baseline,
        "strategy": strategy,
        "feedback": feedback,
        "optimization": optimization,
        "baseline_hourly_rows": baseline_hourly_rows,
        "hourly_rows": hourly_rows,
        "dashboard_rows": dashboard_rows,
    }


def format_demo_output(result: dict[str, Any]) -> str:
    perception = cast(dict[str, Any], result["perception"])
    decision = cast(dict[str, Any], result["decision"])
    feedback = cast(dict[str, Any], result["feedback"])
    optimization = cast(dict[str, Any], result["optimization"])
    strategy = cast(dict[str, Any], result["strategy"])
    llm_status = cast(dict[str, Any], result["llm"])
    hourly_rows = cast(list[dict[str, Any]], result["hourly_rows"])

    key_rows = [
        row
        for row in hourly_rows
        if row["hour"] in {"00:00", "08:00", "11:00", "18:00", "19:00", "23:00"}
    ]

    lines = [
        "电力现货辅助决策 MVP",
        "",
        f"大模型状态：{'已启用' if llm_status['enabled'] else '未启用'}"
        + (f"（{llm_status['model']}）" if llm_status["enabled"] else ""),
        f"预测总负荷：{perception['forecast_total_mwh']:.2f} MWh",
        f"预计日前均价：{perception['average_expected_price_yuan_per_mwh']:.2f} 元/MWh",
        f"策略移峰比例：{decision['effective_shift_ratio'] * 100:.2f}%",
        f"相对基线收益：{feedback['savings_vs_baseline_yuan']:.2f} 元",
        f"策略偏差率：{feedback['strategy_deviation_rate'] * 100:.2f}%",
        f"下一轮推荐移峰比例：{optimization['recommended_shift_ratio'] * 100:.2f}%",
        "",
        "感知结论：",
    ]

    lines.extend(f"- {item}" for item in perception["insights"])
    if perception["llm_summary"]:
        lines.append(f"- 大模型研判：{perception['llm_summary']}")
    lines.append("")
    lines.append(f"决策说明：{decision['strategy_note']}")
    lines.append(f"决策摘要：{decision['decision_highlight']}")
    lines.append("")
    lines.append("反馈诊断：")
    lines.extend(f"- {item}" for item in feedback["diagnosis"])
    lines.append("")
    lines.append("关键时段执行结果：")

    for row in key_rows:
        lines.append(
            "- {hour} | 申报={bid:.2f} | 实际={actual:.2f} | 偏差={dev:.2f} | 成本={cost:.2f}".format(
                hour=row["hour"],
                bid=row["bid_quantity_mwh"],
                actual=row["actual_load_mwh"],
                dev=row["deviation_mwh"],
                cost=row["hour_total_cost_yuan"],
            )
        )

    lines.append("")
    lines.append(f"优化建议：{optimization['recommendation']}")
    lines.append(f"策略总成本：{strategy['total_cost_yuan']:.2f} 元")
    return "\n".join(lines)
