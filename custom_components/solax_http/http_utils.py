"""HTTP endpoint helpers for the SolaX HTTP integration."""

from __future__ import annotations

from urllib.parse import urlparse


def endpoint_urls(host: str) -> list[str]:
    """Return API endpoint URL candidates for a configured host."""
    value = str(host).strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return [value]

    return [f"http://{value}", f"https://{value}"]


def host_for_resolution(host: str) -> str:
    """Return the DNS/IP host portion for config-flow validation."""
    value = str(host).strip()
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return parsed.hostname or ""

    parsed = urlparse(f"//{value}")
    return parsed.hostname or value
