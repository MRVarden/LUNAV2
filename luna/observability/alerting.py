"""Alerting — local webhook notifications on significant events.

Sends alerts via local webhooks when veto events, degradations,
security failures, or other significant events occur.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF protection — URL validation
# ---------------------------------------------------------------------------

_BLOCKED_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
)


def _validate_webhook_url(url: str) -> bool:
    """Validate a webhook URL against SSRF attacks.

    Ensures the URL uses an allowed scheme and does not resolve to a
    private, loopback, or link-local IP address.

    Returns:
        True if the URL is safe to call, False otherwise.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        log.warning("Webhook URL rejected — failed to parse: %s", url)
        return False

    # --- scheme check ---
    if parsed.scheme not in ("http", "https"):
        log.warning(
            "Webhook URL rejected — unsupported scheme '%s': %s",
            parsed.scheme,
            url,
        )
        return False

    hostname = parsed.hostname
    if not hostname:
        log.warning("Webhook URL rejected — no hostname: %s", url)
        return False

    # --- DNS resolution to detect internal IPs ---
    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        log.warning("Webhook URL rejected — DNS resolution failed for '%s'", hostname)
        return False

    for family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            log.warning("Webhook URL rejected — invalid resolved IP '%s'", ip_str)
            return False

        for network in _BLOCKED_NETWORKS:
            if addr in network:
                log.warning(
                    "Webhook URL rejected — resolved IP %s is in blocked range %s: %s",
                    addr,
                    network,
                    url,
                )
                return False

    return True


# ---------------------------------------------------------------------------
# Alert configuration & manager
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AlertConfig:
    """Configuration for the alert manager."""

    on_veto: bool = True
    on_convergence_degrade: bool = True
    on_security_fail: bool = True
    on_phi_iit_below_threshold: bool = True
    on_illusion_detected: bool = True
    webhook_url: str = ""


class AlertManager:
    """Manages alerts for significant system events.

    Sends notifications via local webhooks when configured.
    Maintains a log of recent alerts in memory.
    """

    def __init__(self, config: AlertConfig | None = None) -> None:
        self._config = config or AlertConfig()
        self._alert_history: list[dict] = []
        self._max_history = 100
        # Pre-validate the webhook URL once at init so we fail fast.
        self._webhook_valid: bool = False
        if self._config.webhook_url:
            self._webhook_valid = _validate_webhook_url(self._config.webhook_url)
            if not self._webhook_valid:
                log.error(
                    "Webhook URL failed SSRF validation — webhooks disabled: %s",
                    self._config.webhook_url,
                )

    # ------------------------------------------------------------------
    # Public API — alert() stays synchronous to preserve the interface.
    # ------------------------------------------------------------------

    def alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
        data: dict | None = None,
    ) -> bool:
        """Send an alert.

        Args:
            alert_type: Type of alert (veto, degradation, security, etc.).
            message: Human-readable message.
            severity: Alert severity (info, warning, critical).
            data: Additional data to include.

        Returns:
            True if the alert was processed (not necessarily delivered).
        """
        if not self._should_alert(alert_type):
            return False

        alert_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": alert_type,
            "message": message,
            "severity": severity,
            "data": data or {},
        }

        self._alert_history.append(alert_record)
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history :]

        log.warning("ALERT [%s/%s]: %s", severity, alert_type, message)

        if self._config.webhook_url and self._webhook_valid:
            self._fire_webhook(alert_record)

        return True

    # ------------------------------------------------------------------
    # Webhook delivery — async with graceful fallback
    # ------------------------------------------------------------------

    def _fire_webhook(self, alert_record: dict) -> None:
        """Schedule the async webhook send.

        If an asyncio event loop is already running we create a task;
        otherwise we fall back to a plain thread so that callers in a
        purely synchronous context are not broken.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            loop.create_task(self._send_webhook_async(alert_record))
        else:
            # No running loop — run blocking send in a daemon thread
            # so we never block the caller.
            import threading

            t = threading.Thread(
                target=self._send_webhook_sync,
                args=(alert_record,),
                daemon=True,
            )
            t.start()

    async def _send_webhook_async(self, alert_record: dict) -> None:
        """Send alert via webhook asynchronously (best-effort).

        Offloads the blocking ``urlopen`` call to a thread via
        ``asyncio.to_thread`` so the event loop is never blocked.
        """
        try:
            await asyncio.to_thread(self._send_webhook_sync, alert_record)
        except Exception as exc:  # noqa: BLE001
            log.debug("Alert webhook async delivery failed: %s", exc)

    def _send_webhook_sync(self, alert_record: dict) -> None:
        """Blocking webhook POST — only called from a background thread."""
        try:
            payload = json.dumps(alert_record).encode("utf-8")
            req = urllib.request.Request(
                self._config.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)  # noqa: S310
            log.debug("Alert webhook sent to %s", self._config.webhook_url)
        except Exception as exc:  # noqa: BLE001
            log.debug("Alert webhook failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_alert(self, alert_type: str) -> bool:
        """Check if this alert type is enabled."""
        type_map = {
            "veto": self._config.on_veto,
            "convergence_degrade": self._config.on_convergence_degrade,
            "security_fail": self._config.on_security_fail,
            "phi_iit_low": self._config.on_phi_iit_below_threshold,
            "illusion": self._config.on_illusion_detected,
        }
        return type_map.get(alert_type, True)

    # ------------------------------------------------------------------
    # Public read-only helpers
    # ------------------------------------------------------------------

    @property
    def recent_alerts(self) -> list[dict]:
        """Return recent alert history."""
        return list(self._alert_history)

    def clear_history(self) -> None:
        """Clear alert history."""
        self._alert_history.clear()

    def get_status(self) -> dict:
        """Return current alert manager status."""
        return {
            "webhook_configured": bool(self._config.webhook_url),
            "recent_alert_count": len(self._alert_history),
            "on_veto": self._config.on_veto,
            "on_convergence_degrade": self._config.on_convergence_degrade,
            "on_security_fail": self._config.on_security_fail,
        }
