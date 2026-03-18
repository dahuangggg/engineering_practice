from __future__ import annotations

from dataclasses import dataclass


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


@dataclass
class MarketRules:
    deviation_penalty_yuan_per_mwh: float
    surplus_credit_discount: float
    max_shift_ratio: float
    response_ratio: float


@dataclass
class MarketScenario:
    history_loads: list[list[float]]
    history_prices: list[list[float]]
    forecast_load: list[float]
    expected_dayahead_price: list[float]
    actual_load: list[float]
    actual_dayahead_price: list[float]
    realtime_price: list[float]


@dataclass
class MarketState:
    scenario: MarketScenario
    rules: MarketRules
    risk_preference: str
    risk_factor: float
    shift_ratio: float
    peak_hours: list[int]
    valley_hours: list[int]
    insights: list[str]
    market_regime: str
    llm_summary: str
    rule_parser: str
