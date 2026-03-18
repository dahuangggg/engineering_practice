import unittest

from src.power_market_mvp.core import (
    load_rules_text,
    parse_market_rules,
    run_closed_loop,
)
from src.power_market_mvp.scenario import build_custom_scenario


class MVPSmokeTests(unittest.TestCase):
    def test_parse_rules(self) -> None:
        rules = parse_market_rules(load_rules_text())
        self.assertAlmostEqual(rules.deviation_penalty_yuan_per_mwh, 18.0)
        self.assertAlmostEqual(rules.surplus_credit_discount, 0.88)
        self.assertAlmostEqual(rules.max_shift_ratio, 0.12)
        self.assertAlmostEqual(rules.response_ratio, 0.80)

    def test_closed_loop_runs(self) -> None:
        result = run_closed_loop()
        self.assertEqual(len(result["hourly_rows"]), 24)
        self.assertEqual(len(result["dashboard_rows"]), 24)
        self.assertGreater(result["strategy"]["total_cost_yuan"], 0.0)

    def test_daily_bid_energy_is_conserved(self) -> None:
        result = run_closed_loop()
        forecast_total = result["perception"]["forecast_total_mwh"]
        bid_total = result["decision"]["daily_bid_total_mwh"]
        self.assertAlmostEqual(forecast_total, bid_total, places=1)

    def test_strategy_saves_cost(self) -> None:
        result = run_closed_loop("balanced")
        self.assertGreater(result["feedback"]["savings_vs_baseline_yuan"], 0.0)

    def test_peak_scenario_with_override_runs(self) -> None:
        result = run_closed_loop(
            risk_preference="aggressive",
            scenario_profile="peak",
            rule_overrides={"response_ratio": 0.75, "max_shift_ratio": 0.14},
        )
        self.assertEqual(result["scenario_profile"], "peak")
        self.assertGreater(result["optimization"]["recommended_shift_ratio"], 0.0)

    def test_custom_scenario_runs(self) -> None:
        custom_scenario = build_custom_scenario(
            forecast_load=[60.0 + hour for hour in range(24)],
            expected_dayahead_price=[300.0 + hour * 5 for hour in range(24)],
            actual_load=[61.0 + hour for hour in range(24)],
            actual_dayahead_price=[302.0 + hour * 5 for hour in range(24)],
            realtime_price=[310.0 + hour * 5 for hour in range(24)],
        )
        result = run_closed_loop(custom_scenario=custom_scenario)
        self.assertEqual(result["scenario_profile"], "custom")
        self.assertEqual(result["scenario_display_name"], "自定义数据")
        self.assertEqual(len(result["hourly_rows"]), 24)


if __name__ == "__main__":
    unittest.main()
