from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import statistics
from typing import Any, Dict, List, cast


RISK_FACTORS = {
    "conservative": 0.35,
    "balanced": 0.65,
    "aggressive": 1.00,
}

RISK_LABELS = {
    "conservative": "稳健",
    "balanced": "平衡",
    "aggressive": "进取",
}

LOAD_TEMPLATE = [
    61.0,
    59.0,
    58.0,
    57.0,
    58.0,
    62.0,
    69.0,
    75.0,
    82.0,
    88.0,
    92.0,
    95.0,
    96.0,
    95.0,
    93.0,
    91.0,
    92.0,
    97.0,
    104.0,
    108.0,
    103.0,
    94.0,
    83.0,
    72.0,
]

PRICE_TEMPLATE = [
    275.0,
    268.0,
    263.0,
    258.0,
    260.0,
    268.0,
    285.0,
    318.0,
    356.0,
    404.0,
    448.0,
    486.0,
    476.0,
    452.0,
    428.0,
    412.0,
    422.0,
    468.0,
    516.0,
    536.0,
    498.0,
    432.0,
    362.0,
    308.0,
]

REALTIME_SPREAD_TEMPLATE = [
    6.0,
    5.0,
    5.0,
    4.0,
    4.0,
    5.0,
    7.0,
    11.0,
    17.0,
    23.0,
    29.0,
    34.0,
    28.0,
    21.0,
    18.0,
    16.0,
    18.0,
    27.0,
    36.0,
    40.0,
    31.0,
    22.0,
    14.0,
    9.0,
]

SCENARIO_PROFILES = {
    "stable": {
        "display_name": "平稳日",
        "load_scale": 0.98,
        "price_scale": 0.96,
        "history_load_wave": 0.8,
        "history_price_wave": 0.75,
        "intraday_load_wave": 0.75,
        "intraday_price_wave": 0.7,
        "spread_scale": 0.8,
    },
    "peak": {
        "display_name": "尖峰日",
        "load_scale": 1.08,
        "price_scale": 1.12,
        "history_load_wave": 1.05,
        "history_price_wave": 1.1,
        "intraday_load_wave": 1.1,
        "intraday_price_wave": 1.18,
        "spread_scale": 1.15,
    },
    "volatile": {
        "display_name": "波动日",
        "load_scale": 1.02,
        "price_scale": 1.04,
        "history_load_wave": 1.18,
        "history_price_wave": 1.28,
        "intraday_load_wave": 1.25,
        "intraday_price_wave": 1.35,
        "spread_scale": 1.35,
    },
}


@dataclass
class MarketRules:
    deviation_penalty_yuan_per_mwh: float
    surplus_credit_discount: float
    max_shift_ratio: float
    response_ratio: float


@dataclass
class MarketScenario:
    history_loads: List[List[float]]
    history_prices: List[List[float]]
    forecast_load: List[float]
    expected_dayahead_price: List[float]
    actual_load: List[float]
    actual_dayahead_price: List[float]
    realtime_price: List[float]


@dataclass
class MarketState:
    scenario: MarketScenario
    rules: MarketRules
    risk_preference: str
    risk_factor: float
    shift_ratio: float
    peak_hours: List[int]
    valley_hours: List[int]
    insights: List[str]


def default_rules_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "market_rules.txt"


def load_rules_text(path: str | Path | None = None) -> str:
    rules_path = Path(path) if path else default_rules_path()
    return rules_path.read_text(encoding="utf-8")


def parse_market_rules(text: str) -> MarketRules:
    return MarketRules(
        deviation_penalty_yuan_per_mwh=_extract_number(
            r"Deviation penalty:\s*([0-9.]+)", text, 18.0
        ),
        surplus_credit_discount=_extract_number(r"credited at\s*([0-9.]+)%", text, 88.0)
        / 100.0,
        max_shift_ratio=_extract_number(
            r"up to\s*([0-9.]+)%\s*of forecast load", text, 12.0
        )
        / 100.0,
        response_ratio=_extract_number(
            r"Only\s*([0-9.]+)%\s*of the planned load shift", text, 80.0
        )
        / 100.0,
    )


def _extract_number(pattern: str, text: str, default: float) -> float:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    return float(match.group(1))


def resolve_scenario_profile(profile: str) -> tuple[str, Dict[str, float | str]]:
    normalized_profile = profile.strip().lower()
    if normalized_profile not in SCENARIO_PROFILES:
        normalized_profile = "stable"
    return normalized_profile, SCENARIO_PROFILES[normalized_profile]


def available_scenario_options() -> Dict[str, str]:
    return {
        key: str(config["display_name"]) for key, config in SCENARIO_PROFILES.items()
    }


def apply_rule_overrides(
    rules: MarketRules, overrides: Dict[str, float] | None = None
) -> MarketRules:
    if not overrides:
        return rules

    return MarketRules(
        deviation_penalty_yuan_per_mwh=max(
            0.0,
            float(
                overrides.get(
                    "deviation_penalty_yuan_per_mwh",
                    rules.deviation_penalty_yuan_per_mwh,
                )
            ),
        ),
        surplus_credit_discount=min(
            1.0,
            max(
                0.0,
                float(
                    overrides.get(
                        "surplus_credit_discount", rules.surplus_credit_discount
                    )
                ),
            ),
        ),
        max_shift_ratio=min(
            0.4,
            max(0.0, float(overrides.get("max_shift_ratio", rules.max_shift_ratio))),
        ),
        response_ratio=min(
            1.0,
            max(0.0, float(overrides.get("response_ratio", rules.response_ratio))),
        ),
    )


def _scenario_load_adjustment(profile_key: str, hour: int) -> float:
    if profile_key == "peak":
        if 9 <= hour <= 11:
            return 4.6
        if 17 <= hour <= 21:
            return 8.2
        if 0 <= hour <= 5:
            return 1.2
    if profile_key == "volatile":
        if 6 <= hour <= 8:
            return -2.8
        if 12 <= hour <= 14:
            return 4.4
        if 18 <= hour <= 20:
            return 5.8
        if hour == 23:
            return -2.0
    return 0.0


def _scenario_price_adjustment(profile_key: str, hour: int) -> float:
    if profile_key == "peak":
        if 10 <= hour <= 12:
            return 24.0
        if 17 <= hour <= 20:
            return 48.0
        if 1 <= hour <= 4:
            return -8.0
    if profile_key == "volatile":
        if 7 <= hour <= 8:
            return -14.0
        if 11 <= hour <= 13:
            return 22.0
        if 18 <= hour <= 20:
            return 34.0
        if 22 <= hour <= 23:
            return -10.0
    return 0.0


def _scenario_realtime_adjustment(profile_key: str, hour: int) -> float:
    if profile_key == "peak":
        if 17 <= hour <= 20:
            return 10.0
        if 10 <= hour <= 12:
            return 6.0
    if profile_key == "volatile":
        if 8 <= hour <= 9:
            return 9.0
        if 17 <= hour <= 19:
            return 14.0
        if hour == 22:
            return -4.0
    return 0.0


def build_sample_scenario(
    history_days: int = 5, profile: str = "stable"
) -> MarketScenario:
    profile_key, profile_config = resolve_scenario_profile(profile)
    load_scale = float(profile_config["load_scale"])
    price_scale = float(profile_config["price_scale"])
    history_load_wave = float(profile_config["history_load_wave"])
    history_price_wave = float(profile_config["history_price_wave"])
    intraday_load_wave = float(profile_config["intraday_load_wave"])
    intraday_price_wave = float(profile_config["intraday_price_wave"])
    spread_scale = float(profile_config["spread_scale"])

    history_loads: List[List[float]] = []
    history_prices: List[List[float]] = []

    for day in range(history_days):
        day_loads: List[float] = []
        day_prices: List[float] = []
        load_bias = -2.5 + day * 0.9
        price_bias = day * 5.5

        for hour in range(24):
            load_noise = (
                history_load_wave * 2.4 * math.sin((day + 1) * (hour + 3) / 11.0)
            )
            price_noise = (
                history_price_wave * 7.5 * math.cos((day + 2) * (hour + 1) / 14.0)
            )
            day_loads.append(
                round(
                    LOAD_TEMPLATE[hour] * load_scale
                    + load_bias
                    + load_noise
                    + _scenario_load_adjustment(profile_key, hour),
                    2,
                )
            )
            day_prices.append(
                round(
                    PRICE_TEMPLATE[hour] * price_scale
                    + price_bias
                    + price_noise
                    + _scenario_price_adjustment(profile_key, hour),
                    2,
                )
            )

        history_loads.append(day_loads)
        history_prices.append(day_prices)

    recent_load_days = history_loads[-3:]
    recent_price_days = history_prices[-3:]

    forecast_load: List[float] = []
    expected_dayahead_price: List[float] = []
    actual_load: List[float] = []
    actual_dayahead_price: List[float] = []
    realtime_price: List[float] = []

    for hour in range(24):
        load_forecast = statistics.fmean(day[hour] for day in recent_load_days) + 0.8
        price_forecast = statistics.fmean(
            day[hour] for day in recent_price_days
        ) + intraday_price_wave * 3.5 * math.sin((hour + 2) / 4.0)

        target_load = (
            load_forecast
            + intraday_load_wave * 2.6 * math.sin((hour + 1) / 3.1)
            + _intraday_load_bias(hour)
            + _scenario_load_adjustment(profile_key, hour) * 0.35
        )
        dayahead_price = (
            price_forecast
            + intraday_price_wave * 8.0 * math.sin((hour + 3) / 5.2)
            + _scenario_price_adjustment(profile_key, hour) * 0.25
        )
        realtime = (
            dayahead_price
            + REALTIME_SPREAD_TEMPLATE[hour] * spread_scale
            + 3.0 * math.cos((hour + 1) / 4.2)
            + _scenario_realtime_adjustment(profile_key, hour)
        )

        forecast_load.append(round(load_forecast, 2))
        expected_dayahead_price.append(round(price_forecast, 2))
        actual_load.append(round(target_load, 2))
        actual_dayahead_price.append(round(dayahead_price, 2))
        realtime_price.append(round(realtime, 2))

    return MarketScenario(
        history_loads=history_loads,
        history_prices=history_prices,
        forecast_load=forecast_load,
        expected_dayahead_price=expected_dayahead_price,
        actual_load=actual_load,
        actual_dayahead_price=actual_dayahead_price,
        realtime_price=realtime_price,
    )


def _intraday_load_bias(hour: int) -> float:
    if 9 <= hour <= 11:
        return 0.9
    if 18 <= hour <= 21:
        return 1.6
    if 0 <= hour <= 4:
        return -0.4
    return 0.2


class PerceptionAgent:
    def analyze(
        self,
        scenario: MarketScenario,
        rules_text: str,
        risk_preference: str = "balanced",
        rule_overrides: Dict[str, float] | None = None,
    ) -> MarketState:
        normalized_risk = risk_preference.strip().lower()
        risk_factor = RISK_FACTORS.get(normalized_risk, RISK_FACTORS["balanced"])
        rules = apply_rule_overrides(parse_market_rules(rules_text), rule_overrides)

        ranked_hours = sorted(
            range(24), key=lambda hour: scenario.expected_dayahead_price[hour]
        )
        valley_hours = sorted(ranked_hours[:6])
        peak_hours = sorted(ranked_hours[-6:])

        avg_load = statistics.fmean(scenario.forecast_load)
        avg_price = statistics.fmean(scenario.expected_dayahead_price)
        price_volatility = statistics.pstdev(scenario.expected_dayahead_price)
        shift_ratio = round(rules.max_shift_ratio * risk_factor, 4)

        insights = [
            (
                f"预测平均负荷为 {avg_load:.1f} MWh/h，预计日前市场均价为 {avg_price:.1f} 元/MWh。"
            ),
            (
                f"高价时段为 {format_hours(peak_hours)}，低价时段为 {format_hours(valley_hours)}。"
            ),
            (
                f"价格波动度为 {price_volatility:.1f}；在 {RISK_LABELS.get(normalized_risk, normalized_risk)} 策略下，有效移峰比例为 {shift_ratio * 100:.1f}%。"
            ),
        ]

        return MarketState(
            scenario=scenario,
            rules=rules,
            risk_preference=normalized_risk,
            risk_factor=risk_factor,
            shift_ratio=shift_ratio,
            peak_hours=peak_hours,
            valley_hours=valley_hours,
            insights=insights,
        )


class DecisionAgent:
    def plan(self, state: MarketState) -> Dict[str, Any]:
        forecast = state.scenario.forecast_load
        prices = state.scenario.expected_dayahead_price
        planned_shift = [0.0] * 24
        total_reduction = 0.0

        for hour in state.peak_hours:
            reduction = round(forecast[hour] * state.shift_ratio, 4)
            planned_shift[hour] -= reduction
            total_reduction += reduction

        cheapness_scores = [
            max(prices) - prices[hour] + 1.0 for hour in state.valley_hours
        ]
        cheapness_sum = sum(cheapness_scores)

        for index, hour in enumerate(state.valley_hours):
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
            "effective_shift_ratio": state.shift_ratio,
            "bid_quantities": bid_quantities,
            "planned_shift": planned_shift,
            "shifted_energy_mwh": round(
                sum(value for value in planned_shift if value > 0.0), 2
            ),
            "daily_bid_total_mwh": round(sum(bid_quantities), 2),
            "strategy_note": (
                f"将 {state.shift_ratio * 100:.1f}% 的高价时段预测负荷从 {format_hours(state.peak_hours)} 转移到 {format_hours(state.valley_hours)}。"
            ),
            "rationale": [
                "优先选择低电价时段承接可转移负荷。",
                "保持日总申报电量不变，突出移峰带来的时序价值。",
                "移峰规模直接随风险偏好进行放大或收缩。",
            ],
        }


class ExecutionAgent:
    def simulate(
        self, state: MarketState, planned_shift: List[float], label: str
    ) -> Dict[str, Any]:
        scenario = state.scenario
        rows: List[Dict[str, float | str]] = []
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
        decision: Dict[str, Any],
        baseline: Dict[str, Any],
        strategy: Dict[str, Any],
    ) -> Dict[str, Any]:
        planned_shift = cast(List[float], decision["planned_shift"])
        baseline_total_cost = float(baseline["total_cost_yuan"])
        strategy_total_cost = float(strategy["total_cost_yuan"])
        baseline_deviation_rate = float(baseline["deviation_rate"])
        strategy_deviation_rate = float(strategy["deviation_rate"])

        savings = round(baseline_total_cost - strategy_total_cost, 2)
        deviation_delta = round(strategy_deviation_rate - baseline_deviation_rate, 4)
        shifted_peak_energy = round(
            sum(
                -planned_shift[hour]
                for hour in state.peak_hours
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

        if savings >= 0.0 and strategy_deviation_rate <= 0.06:
            diagnosis.append("当前启发式策略已经足够稳定，可作为课程演示和报告基线。")
        elif savings >= 0.0:
            diagnosis.append("当前策略能够节省成本，但下一轮还需要进一步收紧偏差控制。")
        else:
            diagnosis.append("当前策略移峰过多，下一轮应降低激进程度。")

        return {
            "status": status,
            "savings_vs_baseline_yuan": savings,
            "baseline_total_cost_yuan": baseline_total_cost,
            "strategy_total_cost_yuan": strategy_total_cost,
            "baseline_deviation_rate": baseline_deviation_rate,
            "strategy_deviation_rate": strategy_deviation_rate,
            "diagnosis": diagnosis,
        }


class OptimizationAgent:
    def tune(self, state: MarketState, feedback: Dict[str, Any]) -> Dict[str, Any]:
        current_shift_ratio = state.shift_ratio
        next_shift_ratio = current_shift_ratio
        recommendation = "建议先保持当前策略参数。"
        savings = float(feedback["savings_vs_baseline_yuan"])
        strategy_deviation_rate = float(feedback["strategy_deviation_rate"])

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

        return {
            "current_shift_ratio": round(current_shift_ratio, 4),
            "recommended_shift_ratio": round(next_shift_ratio, 4),
            "recommendation": recommendation,
        }


def build_dashboard_rows(
    state: MarketState,
    decision: Dict[str, Any],
    baseline: Dict[str, Any],
    strategy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    planned_shift = cast(List[float], decision["planned_shift"])
    bid_quantities = cast(List[float], decision["bid_quantities"])
    baseline_rows = cast(List[Dict[str, Any]], baseline["hourly_rows"])
    strategy_rows = cast(List[Dict[str, Any]], strategy["hourly_rows"])

    dashboard_rows: List[Dict[str, Any]] = []

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
                    baseline_hour_cost - strategy_hour_cost,
                    2,
                ),
                "is_peak_hour": hour in state.peak_hours,
                "is_valley_hour": hour in state.valley_hours,
            }
        )

    return dashboard_rows


def run_closed_loop(
    risk_preference: str = "balanced",
    rules_path: str | Path | None = None,
    scenario_profile: str = "stable",
    rule_overrides: Dict[str, float] | None = None,
) -> Dict[str, Any]:
    scenario_key, scenario_config = resolve_scenario_profile(scenario_profile)
    scenario = build_sample_scenario(profile=scenario_key)
    rules_text = load_rules_text(rules_path)

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
    )
    decision = decision_agent.plan(state)
    planned_shift = cast(List[float], decision["planned_shift"])

    baseline = execution_agent.simulate(state, [0.0] * 24, label="baseline")
    strategy = execution_agent.simulate(state, planned_shift, label="strategy")
    feedback = feedback_agent.review(state, decision, baseline, strategy)
    optimization = optimization_agent.tune(state, feedback)
    baseline_hourly_rows = cast(List[Dict[str, Any]], baseline["hourly_rows"])
    hourly_rows = cast(List[Dict[str, Any]], strategy["hourly_rows"])
    dashboard_rows = build_dashboard_rows(state, decision, baseline, strategy)

    return {
        "scenario_profile": scenario_key,
        "scenario_display_name": str(scenario_config["display_name"]),
        "perception": {
            "forecast_total_mwh": round(sum(state.scenario.forecast_load), 2),
            "average_expected_price_yuan_per_mwh": round(
                statistics.fmean(state.scenario.expected_dayahead_price),
                2,
            ),
            "risk_preference": state.risk_preference,
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


def format_demo_output(result: Dict[str, Any]) -> str:
    perception = cast(Dict[str, Any], result["perception"])
    decision = cast(Dict[str, Any], result["decision"])
    feedback = cast(Dict[str, Any], result["feedback"])
    optimization = cast(Dict[str, Any], result["optimization"])
    strategy = cast(Dict[str, Any], result["strategy"])
    hourly_rows = cast(List[Dict[str, Any]], result["hourly_rows"])

    key_rows = [
        row
        for row in hourly_rows
        if row["hour"] in {"00:00", "08:00", "11:00", "18:00", "19:00", "23:00"}
    ]

    lines = [
        "电力现货辅助决策 MVP",
        "",
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
    lines.append("")
    lines.append(f"决策说明：{decision['strategy_note']}")
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


def format_hours(hours: List[int]) -> str:
    return ", ".join(f"{hour:02d}:00" for hour in hours)
