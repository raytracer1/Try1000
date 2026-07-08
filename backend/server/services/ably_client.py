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

    def publish(self, event: str, data: dict):
        """Publish a task to the Ably channel."""
        if not self.api_key:
            logger.warning("No Ably API key — task not dispatched to engine")
            return

        import httpx
        try:
            resp = httpx.post(
                f"{ABLY_URL}/channels/{CHANNEL}/messages",
                headers=self._headers(),
                json={"name": event, "data": json.dumps(data)},
                timeout=5,
            )
            resp.raise_for_status()
            logger.info(f"Ably published: {event} job={data.get('job_id')}")
        except Exception as e:
            logger.error(f"Ably publish failed: {e}")


# Singleton
ably = AblyPublisher(settings.ably_api_key or "")
