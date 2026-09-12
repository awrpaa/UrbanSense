"""
Secure reverse-proxy for TomTom API requests.

Ensures zero client-side exposure of the TOMTOM_API_KEY.
All map tile, style, sprite, glyph, and traffic requests are forwarded
through this proxy with the API key injected server-side.

Reference: https://developer.tomtom.com/maps-sdk-js/guides/security/proxying-api-calls
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────
TOMTOM_BASE_URL = "https://api.tomtom.com"
TOMTOM_API_KEY: str = os.getenv("TOMTOM_API_KEY", "")

UPSTREAM_TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=15.0,
    write=5.0,
    pool=5.0,
)

# Headers that must NOT be forwarded from the upstream response
# (per TomTom proxy guide: strip Content-Encoding, Content-Length,
# Set-Cookie, and upstream CORS headers)
_STRIP_RESPONSE_HEADERS: set[str] = {
    "transfer-encoding",
    "content-encoding",
    "content-length",
    "connection",
    "set-cookie",
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
}

# Headers that must NOT be forwarded to the upstream
_STRIP_REQUEST_HEADERS: set[str] = {
    "cookie",
    "authorization",
    "origin",
    "referer",
    "host",
}

# ── Shared httpx client (connection-pooled) ──────────────────────
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return or create a module-level async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=UPSTREAM_TIMEOUT,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


# ── Response sanitisation ────────────────────────────────────────
def _sanitise_response_body(text: str) -> str:
    """
    Strip the API key from JSON / text response bodies.

    TomTom echoes the real key inside style documents (tile URLs, sprite
    URLs, glyph URLs).  A simple string replacement is the correct tool
    here — walking the JSON tree only creates a way to miss one.

    Reference: "Strip the key back out of the responses"
    https://developer.tomtom.com/maps-sdk-js/guides/security/proxying-api-calls
    """
    if not TOMTOM_API_KEY:
        return text

    # Direct literal replacement — fastest and most reliable
    sanitised = text.replace(TOMTOM_API_KEY, "")

    # Clean up orphaned key= query parameter remnants:
    #   &key=  (middle / trailing param)
    sanitised = re.sub(r"&key=(?=&|\"|\s|$)", "", sanitised)
    #   ?key=& (first param, more follow) → ?
    sanitised = re.sub(r"\?key=&", "?", sanitised)
    #   ?key=  (only param, before quote or EOL) → remove
    sanitised = re.sub(r'\?key=(?=["\s}]|$)', "", sanitised)

    return sanitised


def _filter_response_headers(
    upstream_headers: httpx.Headers,
    content_type: str,
) -> dict[str, str]:
    """Build a safe set of response headers to return to the browser."""
    headers: dict[str, str] = {}
    for key, value in upstream_headers.items():
        if key.lower() not in _STRIP_RESPONSE_HEADERS:
            headers[key] = value
    headers["Content-Type"] = content_type
    return headers


def _build_upstream_headers(request: Request) -> dict[str, str]:
    """
    Build headers to forward upstream, stripping sensitive browser headers
    and injecting the TomTom-Api-Key header (needed for routing requests).
    """
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() not in _STRIP_REQUEST_HEADERS:
            headers[key] = value

    # Drop any client-supplied TomTom-Api-Key before adding our own
    headers.pop("tomtom-api-key", None)
    headers.pop("TomTom-Api-Key", None)
    headers["TomTom-Api-Key"] = TOMTOM_API_KEY

    # Remove host so httpx sets the correct one for api.tomtom.com
    headers.pop("host", None)
    headers.pop("Host", None)
    return headers


# ── Router ───────────────────────────────────────────────────────
router = APIRouter(
    prefix="/api/proxy/tomtom",
    tags=["TomTom Proxy"],
)


async def _proxy_request(
    method: str,
    path: str,
    request: Request,
    body: bytes | None = None,
) -> Response:
    """Core proxy logic shared by GET and POST handlers."""
    if not TOMTOM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="TOMTOM_API_KEY is not configured on the server.",
        )

    # Build upstream URL with API key injected as query parameter
    upstream_url = f"{TOMTOM_BASE_URL}/{path}"
    params = dict(request.query_params)
    params.pop("key", None)  # strip any dummy/leaked key from client
    params["key"] = TOMTOM_API_KEY

    upstream_headers = _build_upstream_headers(request)
    client = _get_client()

    try:
        upstream_resp = await client.request(
            method=method,
            url=upstream_url,
            params=params,
            headers=upstream_headers,
            content=body,
        )
    except httpx.TimeoutException:
        logger.warning("TomTom upstream timeout for: %s %s", method, path)
        raise HTTPException(
            status_code=504,
            detail=f"Upstream TomTom API timed out for: /{path}",
        )
    except httpx.ConnectError:
        logger.error("Cannot connect to TomTom API")
        raise HTTPException(
            status_code=502,
            detail="Could not connect to TomTom API.",
        )
    except httpx.HTTPError as exc:
        logger.error("TomTom proxy error for %s %s: %s", method, path, exc)
        raise HTTPException(
            status_code=502,
            detail=f"TomTom API request failed: {exc}",
        )

    # Forward upstream error status codes
    if upstream_resp.status_code >= 400:
        raise HTTPException(
            status_code=upstream_resp.status_code,
            detail=f"TomTom API returned {upstream_resp.status_code} for /{path}",
        )

    content_type = upstream_resp.headers.get(
        "content-type", "application/octet-stream"
    )

    # ── JSON / text bodies: sanitise to remove leaked API keys ───
    if "json" in content_type or content_type.startswith("text/"):
        body_text = upstream_resp.text
        sanitised = _sanitise_response_body(body_text)

        resp_headers = _filter_response_headers(upstream_resp.headers, content_type)
        resp_headers["Cache-Control"] = "public, max-age=3600"

        return Response(
            content=sanitised,
            status_code=upstream_resp.status_code,
            headers=resp_headers,
        )

    # ── Binary bodies (tiles, sprites, glyphs): stream through ───
    is_tile = any(ext in path for ext in (".pbf", ".png", ".jpg", ".webp"))
    cache_ttl = "public, max-age=86400" if is_tile else "public, max-age=3600"

    resp_headers = _filter_response_headers(upstream_resp.headers, content_type)
    resp_headers["Cache-Control"] = cache_ttl

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )


@router.get("/{path:path}")
async def proxy_tomtom_get(path: str, request: Request) -> Response:
    """Catch-all GET proxy for TomTom API (tiles, styles, sprites, glyphs)."""
    return await _proxy_request("GET", path, request)


@router.post("/{path:path}")
async def proxy_tomtom_post(path: str, request: Request) -> Response:
    """Catch-all POST proxy for TomTom API (routing uses POST with headers)."""
    body = await request.body()
    return await _proxy_request("POST", path, request, body=body)
