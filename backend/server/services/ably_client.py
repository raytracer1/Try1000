"""Ably pub/sub — backend publishes tasks, local engine subscribes."""

from __future__ import annotations

import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "try1000:tasks"

# Ably REST API (publish from backend)
ABLY_URL = "https://rest.ably.io"


class AblyPublisher:
    """Publish task notifications to Ably. Backend side only."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        import base64
        return {
            "Authorization": f"Basic {base64.b64encode(self.api_key.encode()).decode()}",
            "Content-Type": "application/json",
        }

    def notify(self):
        """Wake up the engine: 'there are pending tasks'. No data attached."""
        if not self.api_key:
            return

        import httpx
        try:
            resp = httpx.post(
                f"{ABLY_URL}/channels/{CHANNEL}/messages",
                headers=self._headers(),
                json={"name": "wakeup", "data": "1"},
                timeout=5,
            )
            resp.raise_for_status()
        except Exception:
            pass  # ably is best-effort; polling catches missed wakeups


# Singleton
ably = AblyPublisher(settings.ably_api_key or "")
