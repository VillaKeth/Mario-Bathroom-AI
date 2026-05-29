"""Watchdog — Independent health monitor with auto-restart and degradation tiers.

Run standalone: python server/watchdog.py
Pings /health every 30s, auto-restarts on EMERGENCY, pushes webhook on tier change.
"""

import json
import logging
import os
import subprocess
import sys
import time
from enum import IntEnum
from typing import Optional

logger = logging.getLogger("watchdog")

DEBUG_WATCHDOG = True


class DegradationTier(IntEnum):
    """Service degradation levels — ordered worst to best."""
    EMERGENCY = 0   # Server unreachable, trigger restart
    MINIMAL = 1     # Critical component (TTS/STT) failed
    DEGRADED = 2    # Non-critical slowness (LLM slow)
    FULL = 3        # All systems operational


class Watchdog:
    """Health monitor that tracks server state and decides when to restart."""

    def __init__(self, server_url: str, max_failures: int = 3):
        if DEBUG_WATCHDOG:
            logger.debug("[DEBUG_WATCHDOG] __init__: START server_url=%s max_failures=%d", server_url, max_failures)
        self.server_url = server_url.rstrip("/")
        self.max_failures = max_failures
        self.consecutive_failures = 0
        self.current_tier = DegradationTier.FULL
        self._previous_tier = DegradationTier.FULL
        if DEBUG_WATCHDOG:
            logger.debug("[DEBUG_WATCHDOG] __init__: END")

    def _process_health(self, health_json: dict) -> None:
        """Interpret health response and set degradation tier."""
        if DEBUG_WATCHDOG:
            logger.debug("[DEBUG_WATCHDOG] _process_health: START health=%s", health_json)

        llm_status = health_json.get("llm", "ok")
        tts_status = health_json.get("tts", "ok")
        stt_status = health_json.get("stt", "ok")

        # Determine tier from component statuses (worst wins)
        if tts_status == "failed" or stt_status == "failed":
            self.current_tier = DegradationTier.MINIMAL
        elif llm_status == "slow" or tts_status == "slow" or stt_status == "slow":
            self.current_tier = DegradationTier.DEGRADED
        else:
            self.current_tier = DegradationTier.FULL

        self._record_success()

        if DEBUG_WATCHDOG:
            logger.debug("[DEBUG_WATCHDOG] _process_health: tier=%s", self.current_tier.name)

    def _record_failure(self) -> None:
        """Record a consecutive health check failure."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_failures:
            self.current_tier = DegradationTier.EMERGENCY
        if DEBUG_WATCHDOG:
            logger.debug("[DEBUG_WATCHDOG] _record_failure: count=%d tier=%s", self.consecutive_failures, self.current_tier.name)

    def _record_success(self) -> None:
        """Reset failure counter on successful health check."""
        self.consecutive_failures = 0
        if DEBUG_WATCHDOG:
            logger.debug("[DEBUG_WATCHDOG] _record_success: reset failures, tier=%s", self.current_tier.name)

    def should_restart(self) -> bool:
        """True when consecutive failures have reached the threshold."""
        return self.consecutive_failures >= self.max_failures

    def tier_changed(self) -> bool:
        """Check if tier changed since last call (and update tracking)."""
        changed = self.current_tier != self._previous_tier
        self._previous_tier = self.current_tier
        return changed


def _load_config() -> dict:
    """Load config.json from project root."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _send_webhook(url: str, payload: dict) -> None:
    """POST JSON payload to webhook URL (best-effort)."""
    if not url:
        return
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            client.post(url, json=payload)
        logger.info("Webhook sent to %s", url)
    except Exception as e:
        logger.warning("Webhook failed: %s", e)


def _restart_server() -> Optional[subprocess.Popen]:
    """Restart the Mario AI server via subprocess."""
    server_main = os.path.join(os.path.dirname(__file__), "main.py")
    logger.warning("RESTARTING SERVER: %s", server_main)
    try:
        proc = subprocess.Popen(
            [sys.executable, server_main],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Server restarted (PID=%d)", proc.pid)
        return proc
    except Exception as e:
        logger.error("Failed to restart server: %s", e)
        return None


def main():
    """Standalone watchdog loop — ping /health every 30s, auto-restart on EMERGENCY."""
    # Configure logging
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if DEBUG_WATCHDOG else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "watchdog.log")),
            logging.StreamHandler(),
        ],
    )

    config = _load_config()
    server_config = config.get("server", {})
    port = server_config.get("port", 8765)
    server_url = f"http://localhost:{port}"
    webhook_url = config.get("alert_webhook_url", "")

    wd = Watchdog(server_url, max_failures=3)
    logger.info("Watchdog started — monitoring %s every 30s", server_url)

    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed — run: pip install httpx")
        sys.exit(1)

    while True:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{server_url}/health")
                resp.raise_for_status()
                health = resp.json()

            wd._process_health(health)
            logger.info("Health OK — tier=%s", wd.current_tier.name)

        except Exception as e:
            wd._record_failure()
            logger.warning("Health check failed (%d/%d): %s", wd.consecutive_failures, wd.max_failures, e)

        # Webhook on tier change
        if wd.tier_changed():
            _send_webhook(webhook_url, {
                "event": "tier_change",
                "tier": wd.current_tier.name,
                "failures": wd.consecutive_failures,
                "server_url": server_url,
                "timestamp": time.time(),
            })

        # Auto-restart on EMERGENCY
        if wd.should_restart():
            logger.critical("EMERGENCY — %d consecutive failures, restarting server", wd.consecutive_failures)
            _send_webhook(webhook_url, {
                "event": "restart",
                "tier": "EMERGENCY",
                "failures": wd.consecutive_failures,
                "server_url": server_url,
                "timestamp": time.time(),
            })
            _restart_server()
            # Reset and wait for server to come up
            wd.consecutive_failures = 0
            wd.current_tier = DegradationTier.FULL
            time.sleep(30)
            continue

        time.sleep(30)


if __name__ == "__main__":
    main()
