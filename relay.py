"""
Flash Neo — Multi-User Static-IP HTTPS Relay (Render / VPS)
Allows Flash Neo on Cloudflare Pages (flashneo.pages.dev) to execute live Kotak Neo
orders through each user's own StaticIP.in HTTP/HTTPS/SOCKS5 proxy (sent per-request
via X-Upstream-Proxy) OR through a server-level UPSTREAM_PROXY / VPS static IP.

Security:
- Strictly allowlists ONLY Kotak Securities / Kotak Neo and ipify.org domains.
- Never stores or logs user credentials, tokens, or proxy passwords.
- Optional RELAY_SECRET header check to restrict access to your Cloudflare Pages app.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response

load_dotenv()

DEFAULT_UPSTREAM_PROXY = (os.getenv("UPSTREAM_PROXY") or "").strip() or None
DEFAULT_IP_VERSION = (os.getenv("IP_VERSION") or "auto").strip().lower()  # auto | ipv4 | ipv6
RELAY_SECRET = (os.getenv("RELAY_SECRET") or "").strip() or None

ALLOWED_HOST_SUFFIXES = (
    ".kotaksecurities.com",
    "kotaksecurities.com",
    ".kotakneo.com",
    "kotakneo.com",
    "api4.ipify.org",
    "api6.ipify.org",
)

ALLOWED_PROXY_SCHEMES = {"http", "https", "socks5", "socks5h"}

HOP_BY_HOP_HEADERS = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "x-target-url",
    "x-upstream-proxy",
    "x-ip-version",
    "x-relay-secret",
    "accept-encoding",
    "cf-connecting-ip",
    "cf-ray",
    "cf-visitor",
    "cf-ipcountry",
    "x-forwarded-for",
    "x-forwarded-proto",
    "x-forwarded-host",
    "x-real-ip",
    "render-proxy-ttl",
}

app = FastAPI(title="Flash Neo Multi-User Static-IP Relay", version="2.0.0")


def _is_allowed_target(target_url: str) -> bool:
    try:
        parsed = urlparse(target_url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        return any(host == s or host.endswith(s) for s in ALLOWED_HOST_SUFFIXES)
    except Exception:
        return False


def _validate_proxy(proxy_url: str) -> str:
    cleaned = proxy_url.strip()
    if "://" not in cleaned:
        cleaned = f"http://{cleaned}"
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ALLOWED_PROXY_SCHEMES or not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="Invalid StaticIP proxy URL. Use format: http://user:pass@ip:port",
        )
    return cleaned


def _make_client(upstream_proxy: str | None, ip_version: str) -> httpx.AsyncClient:
    kwargs: dict = {"timeout": 25.0, "follow_redirects": True}
    if upstream_proxy:
        kwargs["proxy"] = upstream_proxy
    elif ip_version == "ipv4":
        kwargs["transport"] = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
    elif ip_version == "ipv6":
        kwargs["transport"] = httpx.AsyncHTTPTransport(local_address="::")
    return httpx.AsyncClient(**kwargs)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Flash Neo Multi-User Relay",
        "per_user_proxy": True,
        "default_proxy_configured": bool(DEFAULT_UPSTREAM_PROXY),
        "secret_protected": bool(RELAY_SECRET),
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def relay(request: Request, path: str = ""):
    target_url = (request.headers.get("x-target-url") or "").strip()
    if not target_url:
        return {
            "status": "Flash Neo Multi-User Relay Running",
            "per_user_proxy": True,
            "secret_protected": bool(RELAY_SECRET),
        }

    if RELAY_SECRET:
        provided = (request.headers.get("x-relay-secret") or "").strip()
        if provided != RELAY_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized relay secret.")

    if not _is_allowed_target(target_url):
        raise HTTPException(status_code=403, detail="Target host not allowed by Flash Neo Relay.")

    req_proxy = (request.headers.get("x-upstream-proxy") or "").strip()
    upstream_proxy = _validate_proxy(req_proxy) if req_proxy else DEFAULT_UPSTREAM_PROXY

    req_ip_ver = (request.headers.get("x-ip-version") or DEFAULT_IP_VERSION).strip().lower()
    if req_ip_ver not in {"auto", "ipv4", "ipv6"}:
        req_ip_ver = "auto"

    forward_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
    }
    body = await request.body()

    try:
        async with _make_client(upstream_proxy, req_ip_ver) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body if body else None,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Relay upstream error: {exc}")

    resp_headers = {}
    if "content-type" in upstream.headers:
        resp_headers["content-type"] = upstream.headers["content-type"]

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
    )
