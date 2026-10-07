"""
NeonTrade risk-based position sizing.

This module calculates an indicative lot size from:
- account equity
- risk percentage
- entry and stop-loss prices
- symbol tick size/value
- broker volume constraints

It deliberately does NOT place orders.
"""

from dataclasses import dataclass
import math


@dataclass
class SymbolSpec:
    tick_size: float
    tick_value: float
    volume_min: float
    volume_max: float
    volume_step: float


def normalize_volume(volume: float, spec: SymbolSpec) -> float:
    volume = max(spec.volume_min, min(spec.volume_max, volume))
    steps = math.floor((volume - spec.volume_min) / spec.volume_step)
    return round(spec.volume_min + steps * spec.volume_step, 8)


def calculate_lot_size(
    equity: float,
    risk_percent: float,
    entry: float,
    stop_loss: float,
    spec: SymbolSpec,
) -> float:
    if equity <= 0:
        raise ValueError("Equity must be positive")
    if not 0 < risk_percent <= 10:
        raise ValueError("Risk percentage must be between 0 and 10")
    distance = abs(entry - stop_loss)
    if distance <= 0:
        raise ValueError("Stop-loss must differ from entry")
    if spec.tick_size <= 0 or spec.tick_value <= 0:
        raise ValueError("Invalid broker tick specification")

    risk_money = equity * (risk_percent / 100.0)
    loss_per_lot = (distance / spec.tick_size) * spec.tick_value
    raw_lots = risk_money / loss_per_lot
    return normalize_volume(raw_lots, spec)
