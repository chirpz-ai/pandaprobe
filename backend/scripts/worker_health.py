"""Lightweight HTTP health server for Celery worker / beat containers.

Runs alongside the Celery process (started in the background via ``&``)
and exposes a ``GET /health`` endpoint that Cloud Run liveness and
startup probes can hit.  The check verifies that the Redis broker is
reachable — if the worker is hung on a dead connection, the probe
fails and Cloud Run restarts the container.

Usage (CI deploy command)::

    python /app/scripts/worker_health.py & exec celery -A ... worker ...
"""

import http.server
import os
import socket


_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_PING_TIMEOUT = 5


def _redis_is_reachable() -> bool:
    """Send a raw Redis PING and check for PONG — no third-party deps."""
    try:
        with socket.create_connection((_REDIS_HOST, _REDIS_PORT), timeout=_PING_TIMEOUT) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            data = sock.recv(64)
            return b"PONG" in data
    except (OSError, ConnectionError):
        return False


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            if _redis_is_reachable():
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"broker unreachable")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = http.server.HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()
