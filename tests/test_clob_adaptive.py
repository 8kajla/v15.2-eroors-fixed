import pytest
from clob_adaptive import CLOBAdaptivePlanner


def item(n, price, regime, created=0, token='T', side='Up'):
    return {
        'status': 'queued', 'notional': n, 'price': price, 'created_at': created,
        'condition': 'C', 'token': token, 'side': side,
        'meta': {'regime': regime}
    }


def test_immediate_ask_is_not_blocked_by_signal_price():
    p = CLOBAdaptivePlanner(max_order=5)
    plan = p.plan([item(4.35, .39, 'MID')], current_ask=.55, min_shares=5, tick_size=.01, now=1)
    assert plan is not None
    assert plan.execution_price == pytest.approx(.55)
    assert plan.requested_budget == pytest.approx(4.35)
    assert plan.topup == pytest.approx(0.0)
    assert plan.max_execution_price > .99


def test_batches_existing_strategy_allocations_without_synthetic_topup():
    p = CLOBAdaptivePlanner(max_order=5, batch_window_seconds=6)
    items = [item(.40, .30, 'MID', created=i) for i in range(8)]
    plan = p.plan(items, current_ask=.51, min_shares=5, tick_size=.01, now=2)
    assert plan is not None
    assert plan.requested_budget >= 2.55
    assert plan.topup == pytest.approx(0.0)


def test_none_current_ask_is_safe_wait():
    p = CLOBAdaptivePlanner()
    assert p.plan([item(1.0, .50, 'MID')], current_ask=None, min_shares=5, tick_size=.01, now=1) is None


def test_invalid_current_ask_is_safe_wait():
    p = CLOBAdaptivePlanner()
    assert p.plan([item(1.0, .50, 'MID')], current_ask='not-a-price', min_shares=5, tick_size=.01, now=1) is None


def test_different_signal_prices_can_be_batched_same_token_side():
    p = CLOBAdaptivePlanner(max_order=5, batch_window_seconds=6)
    items = [item(1.25, .31, 'MID', created=0), item(1.00, .39, 'MID', created=1), item(.75, .35, 'MID', created=2)]
    plan = p.plan(items, current_ask=.55, min_shares=5, tick_size=.01, now=2)
    assert plan is not None
    assert len(plan.items) == 3
    assert plan.requested_budget == pytest.approx(3.0)


def test_does_not_invent_minimum_order_capital():
    p = CLOBAdaptivePlanner()
    plan = p.plan([item(.10, .03, 'CHEAP')], current_ask=.40, min_shares=5, tick_size=.01, now=1)
    assert plan is None


def test_plan_never_exceeds_single_order_cap():
    p = CLOBAdaptivePlanner(max_order=5)
    items = [item(1.0, .80, 'CORE', created=i) for i in range(20)]
    plan = p.plan(items, current_ask=.81, min_shares=5, tick_size=.01, now=5)
    assert plan is not None
    assert plan.requested_budget <= 5.0000001
    assert plan.order_shares * plan.execution_price <= 5.0000001
