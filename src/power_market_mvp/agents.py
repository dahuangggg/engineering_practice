from __future__ import annotations

import statistics
from typing import Any, cast

from .llm import OpenAIJSONAgent
from .models import MarketRules, MarketState, RISK_FACTORS
from .rules import apply_rule_overrides, parse_market_rules
from .scenario import SCENARIO_PROFILES
from .utils import (
    clamp,
    format_hours,
    risk_label,
    safe_float,
    sanitize_hour_list,
    sanitize_text_list,
)


class PerceptionAgent:
    def analyze(
        self,
        scenario,
        rules_text: str,
        risk_preference: str = "balanced",
        rule_overrides: dict[str, float] | None = None,
        llm_agent: OpenAIJSONAgent | None = None,
        scenario_profile: str = "stable",
    ) -> MarketState:
        normalized_risk = risk_preference.strip().lower()
        risk_factor = RISK_FACTORS.get(normalized_risk, RISK_FACTORS["balanced"])
        rules = parse_market_rules(rules_text)
        rule_parser = "regex"

        ranked_hours = sorted(
            range(24), key=lambda hour: scenario.expected_dayahead_price[hour]
        )
        valley_hours = sorted(ranked_hours[:6])
        peak_hours = sorted(ranked_hours[-6:])

        avg_load = statistics.fmean(scenario.forecast_load)
        avg_price = statistics.fmean(scenario.expected_dayahead_price)
        price_volatility = statistics.pstdev(scenario.expected_dayahead_price)
        shift_ratio = round(rules.max_shift_ratio * risk_factor, 4)
        market_regime = f"{SCENARIO_PROFILES.get(scenario_profile, SCENARIO_PROFILES['stable'])['display_name']}市场"
        llm_summary = ""

        insights = [
            f"预测平均负荷为 {avg_load:.1f} MWh/h，预计日前市场均价为 {avg_price:.1f} 元/MWh。",
            f"高价时段为 {format_hours(peak_hours)}，低价时段为 {format_hours(valley_hours)}。",
            f"价格波动度为 {price_volatility:.1f}；在 {risk_label(normalized_risk)} 策略下，有效移峰比例为 {shift_ratio * 100:.1f}%。",
        ]

        if llm_agent is not None:
            system_prompt = (
                "你是电力现货市场感知智能体。"
                "请根据市场规则文本和数值快照，输出 JSON。"
                "数值字段必须是纯数字。"
                "insights 必须是 3 条简洁中文结论。"
                "market_regime 和 market_summary 必须是简洁中文。"
            )
            user_prompt = (
                f"场景预设：{SCENARIO_PROFILES.get(scenario_profile, SCENARIO_PROFILES['stable'])['display_name']}\n"
                f"风险偏好：{risk_label(normalized_risk)}\n"
                f"规则文本：\n{rules_text}\n\n"
                "正则解析得到的默认规则：\n"
                f"- deviation_penalty_yuan_per_mwh={rules.deviation_penalty_yuan_per_mwh}\n"
                f"- surplus_credit_discount={rules.surplus_credit_discount}\n"
                f"- max_shift_ratio={rules.max_shift_ratio}\n"
                f"- response_ratio={rules.response_ratio}\n"
                "市场快照：\n"
                f"- avg_load={avg_load:.2f}\n"
                f"- avg_price={avg_price:.2f}\n"
                f"- price_volatility={price_volatility:.2f}\n"
                f"- peak_hours={peak_hours}\n"
                f"- valley_hours={valley_hours}\n\n"
                "请返回如下 JSON 字段："
                "deviation_penalty_yuan_per_mwh, surplus_credit_discount, max_shift_ratio, response_ratio,"
                "market_regime, market_summary, insights。"
            )
            llm_payload, _ = llm_agent.ask_json(system_prompt, user_prompt)
            if llm_payload:
                rules = MarketRules(
                    deviation_penalty_yuan_per_mwh=clamp(
                        safe_float(
                            llm_payload.get("deviation_penalty_yuan_per_mwh"),
                            rules.deviation_penalty_yuan_per_mwh,
                        ),
                        0.0,
                        100.0,
                    ),
                    surplus_credit_discount=clamp(
                        safe_float(
                            llm_payload.get("surplus_credit_discount"),
                            rules.surplus_credit_discount,
                        ),
                        0.0,
                        1.0,
                    ),
                    max_shift_ratio=clamp(
                        safe_float(
                            llm_payload.get("max_shift_ratio"), rules.max_shift_ratio
                        ),
                        0.0,
                        0.4,
                    ),
                    response_ratio=clamp(
                        safe_float(
                            llm_payload.get("response_ratio"), rules.response_ratio
                        ),
                        0.0,
                        1.0,
                    ),
                )
                rule_parser = "openai+regex"
                market_regime = (
                    str(llm_payload.get("market_regime", market_regime)).strip()
                    or market_regime
                )
                llm_summary = str(llm_payload.get("market_summary", "")).strip()
                insights = sanitize_text_list(
                    llm_payload.get("insights"), insights, limit=3
                )

        rules = apply_rule_overrides(rules, rule_overrides)
        shift_ratio = round(rules.max_shift_ratio * risk_factor, 4)
        insights[2] = (
            f"价格波动度为 {price_volatility:.1f}；在 {risk_label(normalized_risk)} 策略下，有效移峰比例为 {shift_ratio * 100:.1f}%。"
        )

        return MarketState(
            scenario=scenario,
            rules=rules,
            risk_preference=normalized_risk,
            risk_factor=risk_factor,
            shift_ratio=shift_ratio,
            peak_hours=peak_hours,
            valley_hours=valley_hours,
            insights=insights,
            market_regime=market_regime,
            llm_summary=llm_summary,
            rule_parser=rule_parser,
        )


class DecisionAgent:
    def plan(
        self, state: MarketState, llm_agent: OpenAIJSONAgent | None = None
    ) -> dict[str, Any]:
        forecast = state.scenario.forecast_load
        prices = state.scenario.expected_dayahead_price
        planned_shift = [0.0] * 24
        total_reduction = 0.0
        focused_peak_hours = state.peak_hours
        focused_valley_hours = state.valley_hours
        decision_bias = 1.0
        decision_highlight = "围绕高价时段削峰、低价时段填谷，优先保障总体成本下降。"
        rationale = [
            "优先选择低电价时段承接可转移负荷。",
            "保持日总申报电量不变，突出移峰带来的时序价值。",
            "移峰规模直接随风险偏好进行放大或收缩。",
        ]
        decision_source = "heuristic"

        if llm_agent is not None:
            system_prompt = (
                "你是电力现货市场决策智能体。"
                "请根据市场状态和风险偏好，输出 JSON。"
                "focus_peak_hours 与 focus_valley_hours 必须是小时整数列表。"
                "decision_bias 必须是 0.85 到 1.15 之间的数字。"
                "action_summary 和 rationale 必须使用中文。"
            )
            user_prompt = (
                f"市场判断：{state.market_regime}\n"
                f"感知摘要：{state.llm_summary or '基于价格和负荷快照进行常规移峰。'}\n"
                f"风险偏好：{risk_label(state.risk_preference)}\n"
                f"有效基础移峰比例：{state.shift_ratio:.4f}\n"
                f"规则上限 max_shift_ratio：{state.rules.max_shift_ratio:.4f}\n"
                f"候选高价时段：{state.peak_hours}\n"
                f"候选低价时段：{state.valley_hours}\n"
                f"预计日前价格：{[round(price, 2) for price in prices]}\n"
                f"预测负荷：{[round(load, 2) for load in forecast]}\n\n"
                "请返回 JSON 字段：focus_peak_hours, focus_valley_hours, decision_bias, action_summary, rationale。"
            )
            llm_payload, _ = llm_agent.ask_json(system_prompt, user_prompt)
            if llm_payload:
                focused_peak_hours = sanitize_hour_list(
                    llm_payload.get("focus_peak_hours"),
                    state.peak_hours,
                    state.peak_hours,
                )
                focused_valley_hours = sanitize_hour_list(
                    llm_payload.get("focus_valley_hours"),
                    state.valley_hours,
                    state.valley_hours,
                )
                decision_bias = clamp(
                    safe_float(llm_payload.get("decision_bias"), 1.0),
                    0.85,
                    1.15,
                )
                decision_highlight = (
                    str(llm_payload.get("action_summary", decision_highlight)).strip()
                    or decision_highlight
                )
                rationale = sanitize_text_list(
                    llm_payload.get("rationale"), rationale, limit=3
                )
                decision_source = "openai+heuristic"

        effective_shift_ratio = min(
            state.rules.max_shift_ratio,
            round(state.shift_ratio * decision_bias, 4),
        )

        for hour in focused_peak_hours:
            reduction = round(forecast[hour] * effective_shift_ratio, 4)
            planned_shift[hour] -= reduction
            total_reduction += reduction

        cheapness_scores = [
            max(prices) - prices[hour] + 1.0 for hour in focused_valley_hours
        ]
        cheapness_sum = sum(cheapness_scores)

        for index, hour in enumerate(focused_valley_hours):
            addition = total_reduction * cheapness_scores[index] / cheapness_sum
            planned_shift[hour] += addition

        bid_quantities = [
            round(forecast[hour] + planned_shift[hour], 4) for hour in range(24)
        ]
        planned_shift = [
            round(bid_quantities[hour] - forecast[hour], 4) for hour in range(24)
        ]

        return {
            "risk_preference": state.risk_preference,
            "effective_shift_ratio": effective_shift_ratio,
            "decision_bias": round(decision_bias, 4),
            "decision_source": decision_source,
            "focused_peak_hours": focused_peak_hours,
            "focused_valley_hours": focused_valley_hours,
            "bid_quantities": bid_quantities,
            "planned_shift": planned_shift,
            "shifted_energy_mwh": round(
                sum(value for value in planned_shift if value > 0.0), 2
            ),
            "daily_bid_total_mwh": round(sum(bid_quantities), 2),
            "strategy_note": (
                f"将 {effective_shift_ratio * 100:.1f}% 的高价时段预测负荷从 {format_hours(focused_peak_hours)} 转移到 {format_hours(focused_valley_hours)}。"
            ),
            "decision_highlight": decision_highlight,
            "rationale": rationale,
        }


class ExecutionAgent:
    def simulate(
        self, state: MarketState, planned_shift: list[float], label: str
    ) -> dict[str, Any]:
        scenario = state.scenario
        rows: list[dict[str, float | str]] = []
        total_dayahead_cost = 0.0
        total_realtime_cost = 0.0
        total_credit = 0.0
        total_penalty = 0.0
        total_abs_deviation = 0.0
        total_actual_load = 0.0

        for hour in range(24):
            bid_quantity = round(scenario.forecast_load[hour] + planned_shift[hour], 4)
            actual_load = round(
                scenario.actual_load[hour]
                + planned_shift[hour] * state.rules.response_ratio,
                4,
            )
            deviation = round(actual_load - bid_quantity, 4)
            positive_deviation = max(deviation, 0.0)
            negative_deviation = max(-deviation, 0.0)

            day_ahead_cost = round(
                bid_quantity * scenario.actual_dayahead_price[hour], 4
            )
            realtime_cost = round(positive_deviation * scenario.realtime_price[hour], 4)
            credit = round(
                negative_deviation
                * scenario.realtime_price[hour]
                * state.rules.surplus_credit_discount,
                4,
            )
            penalty = round(
                abs(deviation) * state.rules.deviation_penalty_yuan_per_mwh,
                4,
            )
            total_cost = round(day_ahead_cost + realtime_cost - credit + penalty, 4)

            total_dayahead_cost += day_ahead_cost
            total_realtime_cost += realtime_cost
            total_credit += credit
            total_penalty += penalty
            total_abs_deviation += abs(deviation)
            total_actual_load += actual_load

            rows.append(
                {
                    "hour": f"{hour:02d}:00",
                    "bid_quantity_mwh": round(bid_quantity, 2),
                    "actual_load_mwh": round(actual_load, 2),
                    "deviation_mwh": round(deviation, 2),
                    "dayahead_price_yuan_per_mwh": round(
                        scenario.actual_dayahead_price[hour], 2
                    ),
                    "realtime_price_yuan_per_mwh": round(
                        scenario.realtime_price[hour], 2
                    ),
                    "hour_total_cost_yuan": round(total_cost, 2),
                }
            )

        deviation_rate = (
            total_abs_deviation / total_actual_load if total_actual_load else 0.0
        )

        return {
            "label": label,
            "hourly_rows": rows,
            "dayahead_cost_yuan": round(total_dayahead_cost, 2),
            "realtime_cost_yuan": round(total_realtime_cost, 2),
            "surplus_credit_yuan": round(total_credit, 2),
            "penalty_cost_yuan": round(total_penalty, 2),
            "total_cost_yuan": round(
                total_dayahead_cost
                + total_realtime_cost
                - total_credit
                + total_penalty,
                2,
            ),
            "actual_total_load_mwh": round(total_actual_load, 2),
            "deviation_rate": round(deviation_rate, 4),
        }


class FeedbackAgent:
    def review(
        self,
        state: MarketState,
        decision: dict[str, Any],
        baseline: dict[str, Any],
        strategy: dict[str, Any],
        llm_agent: OpenAIJSONAgent | None = None,
    ) -> dict[str, Any]:
        planned_shift = cast(list[float], decision["planned_shift"])
        focused_peak_hours = cast(
            list[int], decision.get("focused_peak_hours", state.peak_hours)
        )
        baseline_total_cost = float(baseline["total_cost_yuan"])
        strategy_total_cost = float(strategy["total_cost_yuan"])
        baseline_deviation_rate = float(baseline["deviation_rate"])
        strategy_deviation_rate = float(strategy["deviation_rate"])

        savings = round(baseline_total_cost - strategy_total_cost, 2)
        deviation_delta = round(strategy_deviation_rate - baseline_deviation_rate, 4)
        shifted_peak_energy = round(
            sum(
                -planned_shift[hour]
                for hour in focused_peak_hours
                if planned_shift[hour] < 0.0
            ),
            2,
        )
        status = "positive" if savings >= 0.0 else "negative"

        diagnosis = [
            f"策略共调整了 {shifted_peak_energy:.2f} MWh 的高价时段申报电量。",
            f"相对基线方案的成本变化为 {savings:.2f} 元。",
            f"偏差率较基线变化了 {deviation_delta * 100:.2f} 个百分点。",
        ]
        optimization_brief = "建议先保持当前策略参数。"
        suggested_shift_delta = 0.0
        diagnosis_source = "heuristic"

        if savings >= 0.0 and strategy_deviation_rate <= 0.06:
            diagnosis.append("当前启发式策略已经足够稳定，可作为课程演示和报告基线。")
        elif savings >= 0.0:
            diagnosis.append("当前策略能够节省成本，但下一轮还需要进一步收紧偏差控制。")
        else:
            diagnosis.append("当前策略移峰过多，下一轮应降低激进程度。")

        if llm_agent is not None:
            system_prompt = (
                "你是电力现货交易复盘智能体。"
                "请根据结算结果做复盘，并输出 JSON。"
                "diagnosis 必须是 3 到 4 条中文短句。"
                "optimization_brief 必须是一句中文建议。"
                "suggested_shift_delta 必须是 -0.03 到 0.03 的数字。"
            )
            user_prompt = (
                f"市场判断：{state.market_regime}\n"
                f"风险偏好：{risk_label(state.risk_preference)}\n"
                f"当前有效移峰比例：{decision['effective_shift_ratio']:.4f}\n"
                f"基线总成本：{baseline_total_cost:.2f}\n"
                f"策略总成本：{strategy_total_cost:.2f}\n"
                f"相对收益：{savings:.2f}\n"
                f"基线偏差率：{baseline_deviation_rate:.4f}\n"
                f"策略偏差率：{strategy_deviation_rate:.4f}\n"
                f"偏差率变化：{deviation_delta:.4f}\n"
                f"高价时段调整电量：{shifted_peak_energy:.2f} MWh\n\n"
                "请返回 JSON 字段：diagnosis, optimization_brief, suggested_shift_delta。"
            )
            llm_payload, _ = llm_agent.ask_json(system_prompt, user_prompt)
            if llm_payload:
                diagnosis = sanitize_text_list(
                    llm_payload.get("diagnosis"), diagnosis, limit=4
                )
                optimization_brief = (
                    str(
                        llm_payload.get("optimization_brief", optimization_brief)
                    ).strip()
                    or optimization_brief
                )
                suggested_shift_delta = clamp(
                    safe_float(llm_payload.get("suggested_shift_delta"), 0.0),
                    -0.03,
                    0.03,
                )
                diagnosis_source = "openai+heuristic"

        return {
            "status": status,
            "savings_vs_baseline_yuan": savings,
            "baseline_total_cost_yuan": baseline_total_cost,
            "strategy_total_cost_yuan": strategy_total_cost,
            "baseline_deviation_rate": baseline_deviation_rate,
            "strategy_deviation_rate": strategy_deviation_rate,
            "diagnosis": diagnosis,
            "optimization_brief": optimization_brief,
            "suggested_shift_delta": suggested_shift_delta,
            "diagnosis_source": diagnosis_source,
        }


class OptimizationAgent:
    def tune(self, state: MarketState, feedback: dict[str, Any]) -> dict[str, Any]:
        current_shift_ratio = state.shift_ratio
        next_shift_ratio = current_shift_ratio
        recommendation = "建议先保持当前策略参数。"
        savings = float(feedback["savings_vs_baseline_yuan"])
        strategy_deviation_rate = float(feedback["strategy_deviation_rate"])
        source = "heuristic"

        if savings > 0.0 and strategy_deviation_rate <= 0.05:
            next_shift_ratio = min(
                state.rules.max_shift_ratio, current_shift_ratio + 0.01
            )
            recommendation = "本轮效果较好，下一轮可以适度提高柔性负荷参与比例。"
        elif strategy_deviation_rate > 0.06:
            next_shift_ratio = max(0.02, current_shift_ratio - 0.015)
            recommendation = "当前偏差偏高，下一轮应降低移峰规模或提升执行确定性。"
        elif savings < 0.0:
            next_shift_ratio = max(0.02, current_shift_ratio - 0.02)
            recommendation = "当前策略尚未形成收益，建议先回调到更稳妥的移峰比例。"

        llm_delta = safe_float(feedback.get("suggested_shift_delta"), 0.0)
        llm_recommendation = str(feedback.get("optimization_brief", "")).strip()
        if llm_delta != 0.0:
            llm_target = clamp(
                current_shift_ratio + llm_delta,
                0.02,
                state.rules.max_shift_ratio,
            )
            next_shift_ratio = round((next_shift_ratio + llm_target) / 2.0, 4)
            if llm_recommendation:
                recommendation = llm_recommendation
            source = "openai+heuristic"

        return {
            "current_shift_ratio": round(current_shift_ratio, 4),
            "recommended_shift_ratio": round(next_shift_ratio, 4),
            "recommendation": recommendation,
            "source": source,
        }
