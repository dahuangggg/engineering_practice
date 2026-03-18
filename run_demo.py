from src.power_market_mvp.core import format_demo_output, run_closed_loop


if __name__ == "__main__":
    result = run_closed_loop(
        risk_preference="balanced",
        llm_enabled=True,
        llm_model="gpt-5-mini",
    )
    print(format_demo_output(result))
