"""
HTTP client for server-side device discovery.
"""

import json
import logging
from typing import Any, List, Optional
from urllib import error, request

LOGGER = logging.getLogger(__name__)


class ServerAPIClient:
    """Small HTTP client that fetches registered devices from the server."""

    DEVICE_ENDPOINTS = ("/api/devices", "/devices")

    def __init__(self, base_url: str, timeout_seconds: float = 6.0):
        self._base_url = (base_url or "").rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_devices(self) -> List[dict]:
        if not self._base_url:
            raise RuntimeError("Base URL is empty")

        last_error = "No endpoint tried"
        for endpoint in self.DEVICE_ENDPOINTS:
            url = f"{self._base_url}{endpoint}"
            try:
                payload = self._get_json(url)
                LOGGER.debug("Fetched API payload from %s", url)
                devices = self._extract_devices(payload)
                if devices is None:
                    raise RuntimeError("JSON shape is not a device list")
                return devices
            except Exception as exc:
                last_error = f"{url} -> {exc}"
                LOGGER.warning("Device endpoint fetch failed: %s", last_error)
        raise RuntimeError(last_error)

    def _get_json(self, url: str) -> Any:
        req = request.Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as resp:
                raw = resp.read()
        except error.URLError as exc:
            raise RuntimeError(f"request failed: {exc}") from exc

        if not raw:
            return []

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON: {exc}") from exc

    def _extract_devices(self, payload: Any) -> Optional[List[dict]]:
        # 1. Direct list
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]

        if isinstance(payload, dict):
            # 2. Known common keys
            for key in ("devices", "data", "items", "results", "result", "payload", "rows"):
                value = payload.get(key)
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    return [row for row in value if isinstance(row, dict)]

            # 3. Aggressive search: look for any list containing dicts
            for key, value in payload.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    return [row for row in value if isinstance(row, dict)]

        return None
