"""Independent DNS/TCP/HTTPS observations; no API keys or response bodies."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
import math
import socket
import ssl
import time
from urllib.parse import urlsplit

import httpx

from . import __version__

TARGETS = {
    "openai": ("OpenAI API", "https://api.openai.com/v1/models"),
    "claude": ("Claude API", "https://api.anthropic.com/v1/models"),
    "gemini": ("Gemini API", "https://generativelanguage.googleapis.com/v1beta/models"),
}


def parse_proxy(value):
    """Validate an HTTP(S) proxy and create a credential-free display URL."""
    if value is None:
        return None, None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError
        host = parsed.hostname
        display_host = f"[{host}]" if ":" in host else host
        return (host, port), f"{parsed.scheme}://{display_host}:{port}"
    except (ValueError, TypeError):
        raise ValueError("Proxy must be an http:// or https:// URL with a valid host and port.") from None


def _dns(host, port, timeout):
    # The system resolver has no portable per-call timeout. Stop waiting after
    # timeout; an unfinished native resolver thread can still delay process exit.
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    try:
        return future.result(timeout=timeout)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _step(name, ok, message, start):
    return {"stage": name, "ok": ok, "message": message,
            "elapsed_ms": round((time.monotonic() - start) * 1000, 2)}


def _tls_error(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, ssl.SSLError):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def status_advice(status):
    if status in (401, 403):
        return "HTTP response received. Check credentials, permissions or access policy; API access is not verified."
    if status == 429:
        return "HTTP response received. Check rate limits and account quota."
    if status == 407:
        return "HTTP response received. Proxy authentication is required; target API reachability is not verified."
    if status >= 500:
        return "HTTP response received. A service or gateway reported an error; retry later."
    if 300 <= status < 400:
        return "HTTP redirect received. Redirects are not followed; inspect the endpoint or gateway."
    return "HTTP response received. This does not verify credentials, quota or model availability."


def diagnose(provider, proxy=None, timeout=5.0):
    if provider not in TARGETS:
        raise ValueError("Unknown provider.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a finite positive number.")
    proxy_endpoint, proxy_display = parse_proxy(proxy)
    name, url = TARGETS[provider]
    destination = urlsplit(url)
    host, port = proxy_endpoint or (destination.hostname, 443)
    steps = []
    report = {
        "version": __version__, "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider, "target": name, "url": url,
        "proxy": proxy_display, "probe_scope": "proxy" if proxy else "target",
        "probe_host": host, "probe_port": port,
        "steps": steps, "http_status": None, "reachable": False,
    }

    start = time.monotonic()
    addresses = []
    try:
        addresses = _dns(host, port, timeout)
        ips = sorted({item[4][0] for item in addresses})
        steps.append(_step("dns", bool(ips), "Resolved: " + ", ".join(ips) if ips else "No addresses returned.", start))
    except (FutureTimeout, socket.timeout):
        steps.append(_step("dns", False, "DNS lookup timed out.", start))
    except OSError:
        steps.append(_step("dns", False, "DNS lookup failed. Check the hostname and DNS configuration.", start))

    start = time.monotonic()
    connected = False
    # Use the resolved addresses so TCP does not perform an unbounded DNS lookup.
    for family, socktype, proto, _, address in addresses:
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            break
        try:
            with socket.socket(family, socktype, proto) as connection:
                connection.settimeout(remaining)
                connection.connect(address)
            connected = True
            break
        except OSError:
            continue
    tcp_message = "TCP connection established." if connected else (
        "TCP not attempted because DNS returned no addresses." if not addresses else
        "TCP connection failed or timed out. Check firewall, routing and proxy port."
    )
    steps.append(_step("tcp", connected, tcp_message, start))

    # Always try HTTPS: it is the decisive observation even if a preliminary
    # lookup failed transiently. Do not read response bodies or follow redirects.
    start = time.monotonic()
    try:
        with httpx.Client(proxy=proxy, timeout=timeout, trust_env=False,
                          follow_redirects=False,
                          headers={"User-Agent": f"ai-netdoctor/{__version__}"}) as client:
            with client.stream("GET", url) as response:
                status = response.status_code
        report["http_status"] = status
        report["reachable"] = status != 407
        steps.append(_step("https", True, f"HTTP {status}: response received.", start))
        report["advice"] = status_advice(status)
    except httpx.TimeoutException:
        steps.append(_step("https", False, "HTTPS request timed out.", start))
        report["advice"] = "Check connectivity and proxy settings, or try a longer timeout."
    except httpx.ProxyError:
        steps.append(_step("https", False, "Proxy connection or CONNECT tunnel failed.", start))
        report["advice"] = "Check proxy protocol, credentials, listening port and upstream routing."
    except (httpx.HTTPError, OSError) as exc:
        tls = _tls_error(exc)
        steps.append(_step("https", False, "TLS verification or handshake failed." if tls else "HTTPS connection failed.", start))
        report["advice"] = ("Check the system clock and trusted certificates; TLS verification remains enabled."
                            if tls else "Check DNS, firewall, routing and proxy configuration.")
    return report
