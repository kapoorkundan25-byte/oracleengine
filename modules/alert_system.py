"""
modules/alert_system.py — Alert System for OracleEngine.

Monitors Polymarket markets in the background and fires user-defined
callbacks whenever a configured condition is met.

Condition types
---------------
* ``PRICE_ABOVE``      — Current probability rises above *threshold*.
* ``PRICE_BELOW``      — Current probability falls below *threshold*.
* ``PRICE_CHANGE_PCT`` — Absolute percentage change exceeds *threshold*.
* ``VOLUME_SPIKE``     — 24-hour volume spikes above *threshold*.
* ``RSI_OVERBOUGHT``   — RSI (14) climbs above *threshold* (default 70).
* ``RSI_OVERSOLD``     — RSI (14) drops below *threshold* (default 30).

Notification channels
---------------------
Built-in callbacks available via factory functions:

* :func:`console_callback` — Logs the alert to the console.
* :func:`webhook_callback` — POSTs the alert payload to a URL.
* :func:`email_callback` — Sends an e-mail via SMTP.
"""

from __future__ import annotations

import json
import smtplib
import threading
import time
import uuid
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable, Literal

import requests

import config
from utils.logger import get_logger

logger = get_logger(__name__)

ConditionType = Literal[
    "PRICE_ABOVE",
    "PRICE_BELOW",
    "PRICE_CHANGE_PCT",
    "VOLUME_SPIKE",
    "RSI_OVERBOUGHT",
    "RSI_OVERSOLD",
]

_ALERTS_FILE = Path("alerts.json")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class AlertCondition:
    """Specification for a single alert condition.

    Attributes:
        market_id:      Polymarket condition ID to watch.
        condition_type: One of the ``ConditionType`` literals.
        threshold:      Numeric trigger value (e.g. 0.7 for 70 %).
        direction:      ``"above"`` or ``"below"`` (used by PRICE_CHANGE_PCT).
        callback:       Callable invoked when the condition is met.
        alert_id:       Auto-generated UUID; override only if necessary.
        active:         Whether the alert is currently being evaluated.
    """

    market_id: str
    condition_type: ConditionType
    threshold: float
    direction: str = "above"
    callback: Callable[[dict[str, Any]], None] = field(
        default_factory=lambda: console_callback, repr=False
    )
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    active: bool = True


# ---------------------------------------------------------------------------
# Built-in notification callbacks
# ---------------------------------------------------------------------------
def console_callback(payload: dict[str, Any]) -> None:
    """Log an alert payload to the console / log file.

    Args:
        payload: Dict describing the triggered alert.
    """
    logger.info(
        "🔔 ALERT — market=%s  condition=%s  value=%.4f  threshold=%.4f",
        payload.get("market_id"),
        payload.get("condition_type"),
        payload.get("current_value", 0),
        payload.get("threshold", 0),
    )


def webhook_callback(url: str | None = None) -> Callable[[dict[str, Any]], None]:
    """Return a callback that POSTs the alert payload to *url*.

    Args:
        url: Webhook URL.  Falls back to ``ALERT_WEBHOOK_URL`` env var.

    Returns:
        A callable suitable for :attr:`AlertCondition.callback`.
    """
    target = url or config.ALERT_WEBHOOK_URL

    def _cb(payload: dict[str, Any]) -> None:
        if not target:
            logger.warning("webhook_callback: no URL configured")
            return
        try:
            resp = requests.post(target, json=payload, timeout=5)
            resp.raise_for_status()
            logger.debug("Webhook delivered to %s", target)
        except Exception as exc:
            logger.error("Webhook delivery failed: %s", exc)

    return _cb


def email_callback(
    to_address: str,
    subject: str = "OracleEngine Alert",
) -> Callable[[dict[str, Any]], None]:
    """Return a callback that sends an e-mail alert via SMTP.

    Args:
        to_address: Recipient e-mail address.
        subject:    E-mail subject line.

    Returns:
        A callable suitable for :attr:`AlertCondition.callback`.
    """

    def _cb(payload: dict[str, Any]) -> None:
        if not all([config.SMTP_HOST, config.SMTP_USER, config.SMTP_PASS]):
            logger.warning("email_callback: SMTP credentials not configured")
            return
        try:
            body = json.dumps(payload, indent=2)
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = config.SMTP_USER
            msg["To"] = to_address
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASS)
                server.sendmail(config.SMTP_USER, to_address, msg.as_string())
            logger.debug("Alert e-mail sent to %s", to_address)
        except Exception as exc:
            logger.error("E-mail delivery failed: %s", exc)

    return _cb


# ---------------------------------------------------------------------------
# Alert Manager
# ---------------------------------------------------------------------------
class AlertManager:
    """Manages alert registration, evaluation, and background monitoring.

    Example::

        mgr = AlertManager()
        mgr.add_alert(AlertCondition(
            market_id="abc123",
            condition_type="PRICE_ABOVE",
            threshold=0.8,
        ))
        mgr.start_monitoring(interval_seconds=30)
        # ... later ...
        mgr.stop_monitoring()
    """

    def __init__(self, alerts_file: Path = _ALERTS_FILE) -> None:
        """Initialise the manager and load any persisted alerts.

        Args:
            alerts_file: Path to the JSON file used for persistence.
        """
        self._alerts: dict[str, AlertCondition] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._alerts_file = alerts_file
        self._load_alerts()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_alerts(self) -> None:
        """Load non-callback alert metadata from the JSON file."""
        if not self._alerts_file.exists():
            return
        try:
            data = json.loads(self._alerts_file.read_text())
            for item in data:
                condition = AlertCondition(
                    market_id=item["market_id"],
                    condition_type=item["condition_type"],
                    threshold=item["threshold"],
                    direction=item.get("direction", "above"),
                    alert_id=item["alert_id"],
                    active=item.get("active", True),
                )
                self._alerts[condition.alert_id] = condition
            logger.info("Loaded %d persisted alerts", len(self._alerts))
        except Exception as exc:
            logger.warning("Could not load persisted alerts: %s", exc)

    def _save_alerts(self) -> None:
        """Persist alert metadata (without callbacks) to the JSON file."""
        try:
            data = [
                {
                    "alert_id": a.alert_id,
                    "market_id": a.market_id,
                    "condition_type": a.condition_type,
                    "threshold": a.threshold,
                    "direction": a.direction,
                    "active": a.active,
                }
                for a in self._alerts.values()
            ]
            self._alerts_file.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("Could not save alerts: %s", exc)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add_alert(self, condition: AlertCondition) -> str:
        """Register a new alert.

        Args:
            condition: The :class:`AlertCondition` to add.

        Returns:
            The ``alert_id`` of the registered alert.
        """
        with self._lock:
            self._alerts[condition.alert_id] = condition
            self._save_alerts()
        logger.info("Added alert %s (%s)", condition.alert_id, condition.condition_type)
        return condition.alert_id

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID.

        Args:
            alert_id: ID returned by :meth:`add_alert`.

        Returns:
            *True* if the alert was found and removed, *False* otherwise.
        """
        with self._lock:
            removed = self._alerts.pop(alert_id, None)
            if removed:
                self._save_alerts()
        if removed:
            logger.info("Removed alert %s", alert_id)
            return True
        logger.warning("Alert %s not found", alert_id)
        return False

    def get_active_alerts(self) -> list[AlertCondition]:
        """Return a list of all active (non-disabled) alerts.

        Returns:
            Snapshot list of active :class:`AlertCondition` objects.
        """
        with self._lock:
            return [a for a in self._alerts.values() if a.active]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def check_alerts(self) -> int:
        """Evaluate all active alerts against current market data.

        Fetches fresh data for each unique market referenced by active
        alerts and fires the corresponding callback when a condition is met.

        Returns:
            Number of alerts that fired.
        """
        # Import here to avoid circular imports at module level
        from modules.data_fetcher import get_market_by_id, get_market_trades
        from modules.trend_analyzer import calculate_rsi

        active = self.get_active_alerts()
        if not active:
            return 0

        # Group by market to minimise API calls
        market_ids = {a.market_id for a in active}
        market_data: dict[str, dict[str, Any]] = {}

        for mid in market_ids:
            try:
                market = get_market_by_id(mid)
                if market is None:
                    continue
                price = market.outcome_prices[0] if market.outcome_prices else 0.0
                trades = get_market_trades(mid, limit=50)
                trade_sizes = [
                    float(t.size) for t in trades if t.size
                ]
                prices_series = [float(t.price) for t in trades if t.price]
                rsi_val = float("nan")
                if len(prices_series) >= 14:
                    import pandas as pd

                    rsi_series = calculate_rsi(pd.Series(prices_series))
                    rsi_val = float(rsi_series.iloc[-1])
                volume_24h = market.volume_24h
                market_data[mid] = {
                    "price": price,
                    "volume_24h": volume_24h,
                    "rsi": rsi_val,
                    "trade_sizes": trade_sizes,
                }
            except Exception as exc:
                logger.warning("Could not fetch data for market %s: %s", mid, exc)

        fired = 0
        for alert in active:
            data = market_data.get(alert.market_id)
            if data is None:
                continue
            triggered, current_value = self._evaluate(alert, data)
            if triggered:
                payload: dict[str, Any] = {
                    "alert_id": alert.alert_id,
                    "market_id": alert.market_id,
                    "condition_type": alert.condition_type,
                    "threshold": alert.threshold,
                    "current_value": current_value,
                }
                try:
                    alert.callback(payload)
                except Exception as exc:
                    logger.error("Alert callback raised: %s", exc)
                fired += 1

        return fired

    @staticmethod
    def _evaluate(
        alert: AlertCondition, data: dict[str, Any]
    ) -> tuple[bool, float]:
        """Evaluate a single alert condition against *data*.

        Returns:
            Tuple of (triggered, current_value).
        """
        ct = alert.condition_type
        price: float = data.get("price", 0.0)
        volume: float = data.get("volume_24h", 0.0)
        rsi: float = data.get("rsi", float("nan"))

        if ct == "PRICE_ABOVE":
            return price > alert.threshold, price
        if ct == "PRICE_BELOW":
            return price < alert.threshold, price
        if ct == "PRICE_CHANGE_PCT":
            # Requires a baseline — skip when no baseline stored
            return False, price
        if ct == "VOLUME_SPIKE":
            return volume > alert.threshold, volume
        if ct == "RSI_OVERBOUGHT":
            threshold = alert.threshold if alert.threshold else 70.0
            import math
            return (not math.isnan(rsi) and rsi > threshold), rsi
        if ct == "RSI_OVERSOLD":
            threshold = alert.threshold if alert.threshold else 30.0
            import math
            return (not math.isnan(rsi) and rsi < threshold), rsi
        return False, 0.0

    # ------------------------------------------------------------------
    # Background monitoring
    # ------------------------------------------------------------------
    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """Start a background thread that polls at *interval_seconds*.

        Args:
            interval_seconds: Polling interval in seconds.
        """
        if self._thread and self._thread.is_alive():
            logger.warning("Monitoring already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True,
            name="OracleEngineMonitor",
        )
        self._thread.start()
        logger.info("Monitoring started (interval=%ds)", interval_seconds)

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Monitoring stopped")

    def _monitoring_loop(self, interval: int) -> None:
        """Internal polling loop — runs in a daemon thread."""
        while not self._stop_event.is_set():
            try:
                fired = self.check_alerts()
                logger.debug("Alert check complete — %d fired", fired)
            except Exception as exc:
                logger.error("Error in monitoring loop: %s", exc)
            self._stop_event.wait(timeout=interval)
