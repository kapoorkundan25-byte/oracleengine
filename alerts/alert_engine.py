"""
alerts/alert_engine.py — Rule-based alert system with console, webhook, and file logging.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from rich.console import Console

import config

logger = logging.getLogger(__name__)
console = Console()

# ── Alert rule dataclasses ─────────────────────────────────────────────────────

@dataclass
class AlertRule:
    market_id: str
    name: str = ""

    def check(self, data: dict) -> Optional[str]:
        """Return a human-readable alert message, or None if rule not triggered."""
        raise NotImplementedError


@dataclass
class PriceAboveThreshold(AlertRule):
    threshold: float = 0.0
    name: str = "PriceAboveThreshold"

    def check(self, data: dict) -> Optional[str]:
        price = data.get("yes_price", 0.0)
        if price > self.threshold:
            return f"[{self.market_id}] YES price {price:.3f} > threshold {self.threshold:.3f}"
        return None


@dataclass
class PriceBelowThreshold(AlertRule):
    threshold: float = 0.0
    name: str = "PriceBelowThreshold"

    def check(self, data: dict) -> Optional[str]:
        price = data.get("yes_price", 0.0)
        if price < self.threshold:
            return f"[{self.market_id}] YES price {price:.3f} < threshold {self.threshold:.3f}"
        return None


@dataclass
class RSIAbove(AlertRule):
    rsi_value: float = 70.0
    name: str = "RSIAbove"

    def check(self, data: dict) -> Optional[str]:
        rsi_val = data.get("rsi_14")
        if rsi_val is not None and rsi_val > self.rsi_value:
            return f"[{self.market_id}] RSI {rsi_val:.1f} > {self.rsi_value:.1f} (overbought)"
        return None


@dataclass
class RSIBelow(AlertRule):
    rsi_value: float = 30.0
    name: str = "RSIBelow"

    def check(self, data: dict) -> Optional[str]:
        rsi_val = data.get("rsi_14")
        if rsi_val is not None and rsi_val < self.rsi_value:
            return f"[{self.market_id}] RSI {rsi_val:.1f} < {self.rsi_value:.1f} (oversold)"
        return None


@dataclass
class VolumeSurge(AlertRule):
    multiplier: float = 3.0
    name: str = "VolumeSurge"

    def check(self, data: dict) -> Optional[str]:
        volume = data.get("volume_24h", 0.0)
        avg_volume = data.get("avg_volume", 0.0)
        if avg_volume > 0 and volume > avg_volume * self.multiplier:
            return (
                f"[{self.market_id}] Volume surge: {volume:.0f} "
                f"is {volume / avg_volume:.1f}x avg ({avg_volume:.0f})"
            )
        return None


@dataclass
class LiquidityDrop(AlertRule):
    drop_pct: float = 20.0  # percentage drop
    name: str = "LiquidityDrop"

    def check(self, data: dict) -> Optional[str]:
        liquidity = data.get("liquidity", 0.0)
        prev_liquidity = data.get("prev_liquidity")
        if prev_liquidity and prev_liquidity > 0:
            drop = (prev_liquidity - liquidity) / prev_liquidity * 100
            if drop >= self.drop_pct:
                return (
                    f"[{self.market_id}] Liquidity dropped {drop:.1f}% "
                    f"(${prev_liquidity:.0f} → ${liquidity:.0f})"
                )
        return None


# ── Alert engine ───────────────────────────────────────────────────────────────

class AlertEngine:
    """
    Evaluate a list of :class:`AlertRule` objects against market data dicts and
    deliver triggered alerts via console, log file, and optionally a webhook.
    """

    def __init__(
        self,
        rules: Optional[list[AlertRule]] = None,
        cooldown_seconds: int = config.ALERT_COOLDOWN_SECONDS,
        log_file: str = config.ALERTS_LOG_FILE,
        webhook_url: str = config.WEBHOOK_URL,
    ) -> None:
        self.rules: list[AlertRule] = rules or []
        self.cooldown_seconds = cooldown_seconds
        self.log_file = log_file
        self.webhook_url = webhook_url
        # key: (rule_name, market_id) → last fired timestamp
        self._last_fired: dict[tuple[str, str], float] = {}

        # Set up file handler
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self._alert_logger = logging.getLogger("alerts")
        if not self._alert_logger.handlers:
            self._alert_logger.addHandler(file_handler)
            self._alert_logger.setLevel(logging.INFO)

    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)

    def evaluate(self, market_data: dict) -> list[str]:
        """
        Evaluate all rules against *market_data* and return a list of fired alert messages.

        *market_data* should contain at minimum: ``market_id``, ``yes_price``,
        ``rsi_14``, ``volume_24h``, ``avg_volume``, ``liquidity``.
        """
        fired: list[str] = []
        now = time.time()

        for rule in self.rules:
            if rule.market_id != market_data.get("market_id", ""):
                continue
            key = (rule.name, rule.market_id)
            last = self._last_fired.get(key, 0.0)
            if now - last < self.cooldown_seconds:
                continue  # still in cooldown

            message = rule.check(market_data)
            if message:
                self._last_fired[key] = now
                fired.append(message)
                self._deliver(message)

        return fired

    def evaluate_all(self, markets_data: list[dict]) -> list[str]:
        """Convenience method — evaluate all rules across a list of market dicts."""
        all_fired: list[str] = []
        for data in markets_data:
            all_fired.extend(self.evaluate(data))
        return all_fired

    # ── delivery ───────────────────────────────────────────────────────────────

    def _deliver(self, message: str) -> None:
        # 1. Rich console
        console.print(f"[bold red]🔔 ALERT:[/bold red] [yellow]{message}[/yellow]")
        # 2. Log file
        self._alert_logger.warning(message)
        # 3. Webhook (fire and forget)
        if self.webhook_url:
            self._send_webhook(message)

    def _send_webhook(self, message: str) -> None:
        payload: dict[str, Any] = {"text": f":bell: *ALERT* {message}"}
        try:
            httpx.post(self.webhook_url, json=payload, timeout=5)
        except Exception as exc:
            logger.debug("Webhook delivery failed: %s", exc)
