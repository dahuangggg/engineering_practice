from __future__ import annotations

import math
import statistics
from typing import Dict

from .models import MarketScenario


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


def resolve_scenario_profile(profile: str) -> tuple[str, Dict[str, float | str]]:
    normalized_profile = profile.strip().lower()
    if normalized_profile not in SCENARIO_PROFILES:
        normalized_profile = "stable"
    return normalized_profile, SCENARIO_PROFILES[normalized_profile]


def available_scenario_options() -> Dict[str, str]:
    return {
        key: str(config["display_name"]) for key, config in SCENARIO_PROFILES.items()
    }


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


def _intraday_load_bias(hour: int) -> float:
    if 9 <= hour <= 11:
        return 0.9
    if 18 <= hour <= 21:
        return 1.6
    if 0 <= hour <= 4:
        return -0.4
    return 0.2


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

    history_loads: list[list[float]] = []
    history_prices: list[list[float]] = []

    for day in range(history_days):
        day_loads: list[float] = []
        day_prices: list[float] = []
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

    forecast_load: list[float] = []
    expected_dayahead_price: list[float] = []
    actual_load: list[float] = []
    actual_dayahead_price: list[float] = []
    realtime_price: list[float] = []

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
