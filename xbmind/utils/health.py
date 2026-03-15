"""HTTP health check server.

Runs an ``aiohttp`` server on ``localhost:7070/health`` (configurable)
that returns the current component statuses as JSON.  Useful for systemd
watchdog and external monitoring.
"""

from __future__ import annotations

import time
from typing import Any

from aiohttp import web

from xbmind.utils.logger import get_logger

log = get_logger(__name__)


class HealthServer:
    """Lightweight HTTP health check endpoint.

    Example::

        server = HealthServer(host="127.0.0.1", port=7070)
        server.set_status("bluetooth", True)
        await server.start()
        # GET http://127.0.0.1:7070/health → {"status": "ok", ...}
        await server.stop()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7070) -> None:
        """Initialise the health server.

        Args:
            host: Bind address.
            port: Bind port.
        """
        self._host = host
        self._port = port
        self._components: dict[str, bool] = {}
        self._start_time: float = time.monotonic()
        self._app = web.Application()
        self._app.router.add_get("/health", self._handle_health)
        self._runner: web.AppRunner | None = None

    def set_status(self, component: str, healthy: bool) -> None:
        """Update a component's health status.

        Args:
            component: Component name (e.g. ``"bluetooth"``).
            healthy: ``True`` if the component is operating normally.
        """
        self._components[component] = healthy

    async def _handle_health(self, _request: web.Request) -> web.Response:
        """Handle GET /health requests.

        Args:
            _request: The incoming HTTP request (unused).

        Returns:
            JSON response with overall status and per-component details.
        """
        all_healthy = all(self._components.values()) if self._components else True
        uptime_seconds = round(time.monotonic() - self._start_time, 1)

        body: dict[str, Any] = {
            "status": "ok" if all_healthy else "degraded",
            "uptime_seconds": uptime_seconds,
            "components": {
                name: "healthy" if ok else "unhealthy"
                for name, ok in sorted(self._components.items())
            },
        }

        status_code = 200 if all_healthy else 503
        return web.json_response(body, status=status_code)

    async def start(self) -> None:
        """Start the health check HTTP server."""
        self._start_time = time.monotonic()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        log.info("health_server.started", host=self._host, port=self._port)

    async def stop(self) -> None:
        """Stop the health check HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        log.info("health_server.stopped")
