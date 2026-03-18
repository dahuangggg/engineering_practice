from __future__ import annotations

from pathlib import Path
import re

from .models import MarketRules


def default_rules_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "market_rules.txt"


def load_rules_text(path: str | Path | None = None) -> str:
    rules_path = Path(path) if path else default_rules_path()
    return rules_path.read_text(encoding="utf-8")


def _extract_number(pattern: str, text: str, default: float) -> float:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    return float(match.group(1))


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


def apply_rule_overrides(
    rules: MarketRules, overrides: dict[str, float] | None = None
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
