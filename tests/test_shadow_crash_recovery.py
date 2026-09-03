import os
from pathlib import Path


def test_bot_contains_shadow_stale_halt_reset():
    src = Path(__file__).parents[1] / "bot.py"
    text = src.read_text()
    assert "SHADOW RISK RESET" in text
    assert 'risk.halt_reason not in {"DAILY_LOSS_CAP", "CORRUPT_RISK_STATE"}' in text


def test_live_remains_fail_closed_on_loop_error():
    src = Path(__file__).parents[1] / "bot.py"
    text = src.read_text()
    assert 'if LIVE:' in text
    assert 'LIVE SAFETY STOP: unexpected live-path exception' in text


def test_shadow_subminimum_path_exists():
    src = Path(__file__).parents[1] / "bot.py"
    text = src.read_text()
    assert "SHADOW_SUBMIN_STRATEGY_LOT" in text
    assert "AdaptivePlan(" in text
