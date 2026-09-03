from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_BATCH_WINDOW_SECONDS = 6.0
DEFAULT_MAX_ORDER = 5.0


@dataclass(frozen=True)
class AdaptivePlan:
    items: Tuple[Dict[str, Any], ...]
    execution_price: float
    requested_budget: float
    order_shares: float
    min_order_cost: float
    min_shares: float
    topup: float
    max_execution_price: float


class CLOBAdaptivePlanner:
    """Plan immediate taker execution without changing V15.2 strategy allocation.

    IMPORTANT:
      * The strategy's fine-band, side, cadence, and notional are immutable.
      * The current best ask is an execution input, not a trigger.
      * We do NOT require ask <= signal price or ask <= a spread/uplift ceiling.
      * Exchange minimums are satisfied only by combining already-generated,
        compatible strategy allocations. No synthetic capital is added.
      * A single live order may consume multiple queued allocations only when
        they belong to the same condition/token/side and are FIFO-compatible.
    """

    def __init__(
        self,
        *,
        max_order: float = DEFAULT_MAX_ORDER,
        batch_window_seconds: float = DEFAULT_BATCH_WINDOW_SECONDS,
        **_,
    ):
        self.max_order = max(0.01, float(max_order))
        self.batch_window_seconds = max(0.0, float(batch_window_seconds))

    @staticmethod
    def max_price(signal_price: float, tick_size: float = 0.01, regime: str = "MID") -> float:
        del signal_price, tick_size, regime
        # Kept for metadata/backward compatibility. In immediate-ask mode there
        # is no strategy-price execution ceiling.
        return 0.999999

    def plan(
        self,
        items: Iterable[Dict[str, Any]],
        *,
        current_ask: float,
        min_shares: float,
        tick_size: float,
        now: float,
    ) -> Optional[AdaptivePlan]:
        del tick_size
        try:
            ask = float(current_ask)
            min_s = float(min_shares)
        except (TypeError, ValueError):
            return None
        if not (0.0 < ask < 1.0) or min_s <= 0.0:
            return None

        candidates: List[Dict[str, Any]] = []
        for item in items:
            if str(item.get("status", "queued")) != "queued":
                continue
            expiry = item.get("expires_at")
            if expiry is not None:
                try:
                    if now >= float(expiry):
                        continue
                except (TypeError, ValueError):
                    continue
            try:
                created = float(item.get("created_at", now))
                amount = float(item.get("notional", 0.0))
            except (TypeError, ValueError):
                continue
            if amount <= 0.0:
                continue
            # Old items are still executable immediately; they do not expire just
            # because the batch window elapsed. The batch window only limits which
            # additional signals may be combined with a fresh signal.
            candidates.append(item)

        if not candidates:
            return None
        candidates.sort(key=lambda x: float(x.get("created_at", now)))

        minimum_cost = ask * min_s
        selected: List[Dict[str, Any]] = []
        intended = 0.0
        first_created = float(candidates[0].get("created_at", now))

        for item in candidates:
            created = float(item.get("created_at", now))
            # Do not combine an old signal with a new one after the configured
            # batching horizon. The old signal can still be executed alone.
            if selected and created - first_created > self.batch_window_seconds:
                break
            amount = max(0.0, float(item.get("notional", 0.0)))
            if amount <= 0.0:
                continue
            if intended + amount > self.max_order + 1e-9:
                continue
            selected.append(item)
            intended += amount
            if intended + 1e-9 >= minimum_cost:
                break

        if not selected or intended <= 0.0:
            return None
        if intended + 1e-9 < minimum_cost:
            # Never invent a minimum-order top-up. Wait for another compatible
            # strategy allocation or remain unfilled.
            return None

        budget = min(intended, self.max_order)
        if budget + 1e-9 < minimum_cost:
            return None
        shares = budget / ask
        return AdaptivePlan(
            items=tuple(selected),
            execution_price=ask,
            requested_budget=budget,
            order_shares=shares,
            min_order_cost=minimum_cost,
            min_shares=min_s,
            topup=0.0,
            max_execution_price=0.999999,
        )
