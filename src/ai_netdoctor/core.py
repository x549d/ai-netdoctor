"""Independent DNS/TCP/HTTPS observations with actionable, key-free guidance."""

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


def _step(name, ok, message, start, explanation="", possible_causes=(), recommended_actions=()):
    return {
        "stage": name,
        "ok": ok,
        "message": message,
        "explanation": explanation,
        "possible_causes": list(possible_causes),
        "recommended_actions": list(recommended_actions),
        "elapsed_ms": round((time.monotonic() - start) * 1000, 2),
    }


def _tls_error(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, ssl.SSLError):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def _status_guidance(status):
    """Explain an HTTP response and suggest next steps without claiming API success."""
    if status == 200 or 200 <= status < 300:
        return {
            "explanation": "The HTTPS endpoint returned a successful HTTP response. This confirms that an HTTP server answered, but this unauthenticated probe does not verify API credentials, quota, permissions, or model access.",
            "possible_causes": [],
            "recommended_actions": [
                "If your application still cannot make model requests, check its API key, required headers, project permissions, model availability, and request format."
            ],
        }
    if status == 401:
        return {
            "explanation": "The endpoint requires authentication. AI NetDoctor intentionally sends no API key, so HTTP 401 is commonly an expected result for this connectivity check.",
            "possible_causes": [
                "The diagnostic request contains no API key.",
                "An application request may be using a missing, expired, or incorrectly configured key."
            ],
            "recommended_actions": [
                "If only this diagnostic reports 401, treat it as evidence that the endpoint responded over HTTPS.",
                "If your own API request also reports 401, verify the key in your application's secret or environment configuration and confirm the provider-specific authentication header.",
                "Never paste an API key into a shared diagnostic report or public issue."
            ],
        }
    if status == 403:
        return {
            "explanation": "The server understood the request but refused access. Network connectivity reached an HTTP endpoint; the response may reflect an access policy rather than a network failure.",
            "possible_causes": [
                "IP, region, organization, or project access restrictions.",
                "A firewall, WAF, gateway, or provider policy blocked the request.",
                "The application key or project lacks the required permission."
            ],
            "recommended_actions": [
                "Check the provider's account, organization, project, and regional access policies.",
                "If using a proxy or VPN, compare with a permitted network path and check whether the egress IP is allowed.",
                "If your authenticated request also returns 403, review the key's project permissions and model access."
            ],
        }
    if status == 407:
        return {
            "explanation": "An HTTP proxy requested authentication. The proxy answered, but the connection to the target API has not been confirmed.",
            "possible_causes": [
                "The proxy requires a username and password.",
                "The configured proxy endpoint is an enterprise proxy rather than the expected local proxy.",
                "The proxy URL or authentication settings are incorrect."
            ],
            "recommended_actions": [
                "Check whether the proxy requires credentials and configure them in your local environment without sharing them in logs.",
                "Verify the proxy scheme, host, and port; for a local Clash HTTP/Mixed port, use an http:// URL.",
                "Confirm that the proxy is listening and that its upstream connection works."
            ],
        }
    if status == 429:
        return {
            "explanation": "The server or gateway returned a rate-limit or quota response. An HTTP endpoint was reached, but requests may be throttled.",
            "possible_causes": [
                "Request rate or concurrency is too high.",
                "The account or project has reached a quota or billing limit.",
                "A gateway applies its own rate limit."
            ],
            "recommended_actions": [
                "Check the response headers and provider dashboard for retry timing, rate limits, quota, and billing status.",
                "Reduce request frequency or concurrency and retry after the indicated interval.",
                "If this response comes from a gateway, check that gateway's rate-limit policy."
            ],
        }
    if 300 <= status < 400:
        return {
            "explanation": "The endpoint returned a redirect. AI NetDoctor does not follow redirects, so the result shows the original endpoint answered without silently changing the destination.",
            "possible_causes": [
                "The API base URL or endpoint path has changed.",
                "A proxy, gateway, or captive portal is redirecting the request."
            ],
            "recommended_actions": [
                "Check the provider's official API base URL and endpoint path.",
                "If using a proxy or gateway, verify that it is not rewriting API requests.",
                "If the redirect appears to lead to a login page, check for a captive portal or network access page."
            ],
        }
    if status == 404:
        return {
            "explanation": "The server responded, but the requested path was not found. This is an HTTP endpoint or routing response, not a DNS failure.",
            "possible_causes": [
                "The provider endpoint or API version has changed.",
                "A proxy or gateway rewrote the request path.",
                "The upstream service does not expose this diagnostic path."
            ],
            "recommended_actions": [
                "Compare the target URL with the provider's current API documentation.",
                "Check proxy and gateway path-rewrite rules.",
                "If ordinary application requests work, this diagnostic endpoint may not be supported; do not infer that all API calls are unavailable."
            ],
        }
    if 400 <= status < 500:
        return {
            "explanation": f"The server returned client error HTTP {status}. The HTTP endpoint responded, but it rejected this request.",
            "possible_causes": [
                "The diagnostic GET request is not accepted by this endpoint.",
                "The endpoint expects different parameters, headers, or an API version.",
                "A gateway or access policy rejected the request."
            ],
            "recommended_actions": [
                "Check the provider's endpoint and API documentation.",
                "If your application request also fails, inspect its method, path, headers, and required parameters.",
                "Use the response from your own application request for deeper API-level diagnosis; this tool does not send credentials."
            ],
        }
    if status >= 500:
        return {
            "explanation": f"The server or an intermediary gateway returned HTTP {status}. The request reached an HTTP endpoint, but the service did not return a successful response.",
            "possible_causes": [
                "A temporary provider-side outage or overloaded service.",
                "An upstream gateway, reverse proxy, or network intermediary failure."
            ],
            "recommended_actions": [
                "Check the provider's service-status page and retry after a short interval.",
                "If the error persists, compare direct and proxy routes where permitted.",
                "If only one network path fails, inspect the proxy or gateway upstream configuration."
            ],
        }
    return {
        "explanation": f"The endpoint returned HTTP {status}. This confirms an HTTP response, not successful authentication or model access.",
        "possible_causes": [
            "The endpoint or an intermediary returned a provider-specific status."
        ],
        "recommended_actions": [
            "Check the provider's documentation for this status code.",
            "If your application request also fails, inspect its authentication, permissions, endpoint, and request format."
        ],
    }


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
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "target": name,
        "url": url,
        "proxy": proxy_display,
        "probe_scope": "proxy" if proxy else "target",
        "probe_host": host,
        "probe_port": port,
        "steps": steps,
        "http_status": None,
        "reachable": False,
        "result": "Target reachability not confirmed.",
        "advice": "Review the failed diagnostic stage and its recommended actions.",
        "recommended_actions": [],
    }

    start = time.monotonic()
    addresses = []
    try:
        addresses = _dns(host, port, timeout)
        ips = sorted({item[4][0] for item in addresses})
        if ips:
            steps.append(_step(
                "dns", True, "Resolved: " + ", ".join(ips), start,
                "The hostname used for the connection resolved to one or more IP addresses. "
                "In direct mode this is the API hostname; in proxy mode this is the proxy hostname."
            ))
        else:
            steps.append(_step(
                "dns", False, "No addresses returned.", start,
                "The resolver completed but returned no usable IP addresses.",
                ["The hostname may have no DNS records or the resolver returned an empty result."],
                ["Check that the hostname is correct.", "Try resolving it with nslookup or your system's DNS diagnostic tool."]
            ))
    except (FutureTimeout, socket.timeout):
        steps.append(_step(
            "dns", False, "DNS lookup timed out.", start,
            "The system DNS resolver did not return an answer within the configured wait period.",
            ["The configured DNS server is slow or unreachable.", "A VPN, firewall, or network policy may be interfering with DNS."],
            ["Check that the network is connected and the configured DNS server is reachable.",
             "On Windows, try: ipconfig /flushdns, then retry.",
             "Use nslookup to test the hostname; in proxy mode, the hostname being checked is the proxy host.",
             "Retry with a longer --timeout value."]
        ))
    except socket.gaierror as exc:
        if exc.errno == getattr(socket, "EAI_NONAME", object()):
            explanation = "The DNS resolver reported that the hostname does not exist or could not be found."
            causes = ["The hostname may be misspelled or unavailable in DNS.", "A DNS filter or network policy may be blocking the lookup."]
            actions = ["Check the hostname and proxy URL for spelling errors.",
                       "Run nslookup <hostname> and compare the result with another trusted network.",
                       "If this is a proxy hostname, confirm that it resolves from this computer."]
        elif exc.errno == getattr(socket, "EAI_AGAIN", object()):
            explanation = "The DNS resolver reported a temporary failure."
            causes = ["The DNS server may be temporarily unavailable.", "The network or VPN may be interrupting DNS requests."]
            actions = ["Retry after a short interval.", "Check the configured DNS server and VPN.", "On Windows, try ipconfig /flushdns."]
        else:
            explanation = "The operating system could not resolve the hostname."
            causes = ["The hostname may be invalid or DNS configuration may be unavailable."]
            actions = ["Check the hostname and DNS settings.", "Run nslookup <hostname> to inspect the resolver response."]
        steps.append(_step("dns", False, "DNS lookup failed.", start, explanation, causes, actions))
    except OSError:
        steps.append(_step(
            "dns", False, "DNS lookup failed.", start,
            "The operating system could not complete the hostname lookup.",
            ["The hostname may be invalid.", "The local DNS resolver or network configuration may be unavailable."],
            ["Check the hostname and DNS settings.", "Run nslookup <hostname> to inspect the resolver response."]
        ))

    start = time.monotonic()
    connected = False
    # Use resolved addresses so TCP does not perform another potentially slow DNS lookup.
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
    if connected:
        tcp_message = "TCP connection established."
        tcp_explanation = "A TCP handshake completed with the checked host and port. The network path to this host:port is open at the time of the test."
        tcp_causes = []
        tcp_actions = []
    elif not addresses:
        tcp_message = "TCP not attempted because DNS returned no addresses."
        tcp_explanation = "TCP testing needs an IP address, but the DNS stage did not provide one. Fix or recheck DNS first."
        tcp_causes = ["The preceding DNS lookup failed or returned no addresses."]
        tcp_actions = ["Follow the DNS stage's recommended actions, then run the diagnostic again."]
    else:
        tcp_message = "TCP connection failed or timed out."
        tcp_explanation = "DNS returned an address, but a TCP connection to the checked host and port could not be established."
        if proxy:
            tcp_causes = ["The local proxy may not be running.", "The configured proxy port may be incorrect or not listening.", "A firewall may block the local or upstream connection."]
            tcp_actions = [
                "Confirm the proxy application is running and that --proxy uses its HTTP or Mixed port (not a SOCKS-only port).",
                f"On Windows, test the proxy listener with: Test-NetConnection {host} -Port {port}",
                "Check the proxy's routing mode, firewall rules, and upstream connection."
            ]
        else:
            tcp_causes = ["The destination port may be blocked by a firewall or network policy.", "The network route or VPN may be unavailable.", "The destination may be temporarily unreachable."]
            tcp_actions = [
                f"On Windows, test the route with: Test-NetConnection {host} -Port {port}",
                "Check the firewall, VPN/TUN state, and network routing.",
                "Retry on another permitted network to determine whether the issue is network-specific."
            ]
    steps.append(_step("tcp", connected, tcp_message, start, tcp_explanation, tcp_causes, tcp_actions))

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
        guidance = _status_guidance(status)
        steps.append(_step(
            "https", True, f"HTTP {status}: response received.", start,
            guidance["explanation"], guidance["possible_causes"], guidance["recommended_actions"]
        ))
        report["advice"] = guidance["explanation"]
        report["recommended_actions"] = guidance["recommended_actions"]
        report["result"] = (
            "Proxy authentication required; target API reachability not confirmed."
            if status == 407 else
            f"HTTP endpoint responded with status {status}; API access is not verified."
        )
    except httpx.TimeoutException:
        explanation = "The HTTPS request did not complete within the configured HTTP timeout."
        causes = ["The destination or proxy may be slow or unreachable.", "A firewall, VPN, or proxy route may be dropping or delaying traffic."]
        actions = [
            "Check the DNS and TCP observations above; in proxy mode, verify that the proxy is listening and can reach the internet.",
            "Retry with a longer timeout, for example --timeout 15.",
            "Compare direct and proxy modes where your network and provider policies permit."
        ]
        steps.append(_step("https", False, "HTTPS request timed out.", start, explanation, causes, actions))
        report["advice"] = explanation
        report["recommended_actions"] = actions
    except httpx.ProxyError:
        explanation = "The HTTP client could not establish a connection to the proxy or complete the HTTPS CONNECT tunnel."
        causes = ["The proxy process or port may be unavailable.", "The proxy URL may use the wrong scheme or port.", "Proxy authentication or upstream routing may have failed."]
        actions = [
            "Confirm the proxy is running and check its HTTP/Mixed listener port.",
            "For a local Clash HTTP/Mixed listener, use a URL such as --proxy http://127.0.0.1:7897; do not use a SOCKS port as an HTTP proxy.",
            "On Windows, run Test-NetConnection 127.0.0.1 -Port <proxy-port>.",
            "Check proxy authentication and upstream routing. Do not share proxy credentials in logs."
        ]
        steps.append(_step("https", False, "Proxy connection or CONNECT tunnel failed.", start, explanation, causes, actions))
        report["advice"] = explanation
        report["recommended_actions"] = actions
    except (httpx.HTTPError, OSError) as exc:
        if _tls_error(exc):
            explanation = "The TLS handshake or certificate verification failed. The tool keeps certificate verification enabled to protect the connection."
            causes = ["The system clock may be incorrect.", "The certificate chain may be missing or untrusted.", "A corporate proxy or security product may be intercepting TLS."]
            actions = [
                "Check the computer's date, time, and time zone.",
                "Update the operating system's trusted root certificates.",
                "If your organization inspects HTTPS traffic, ask for its trusted CA certificate and configure trust through a supported system mechanism.",
                "Do not disable TLS certificate verification as a workaround."
            ]
            message = "TLS verification or handshake failed."
        elif isinstance(exc, httpx.ConnectError):
            explanation = "The HTTPS client could not establish a connection to the destination or its proxy."
            causes = ["The network route may be blocked.", "The proxy may be unavailable or unable to reach the upstream host.", "A remote endpoint may have closed or refused the connection."]
            actions = [
                "Review the DNS and TCP stages above.",
                "Check firewall, VPN/TUN, and proxy routing rules.",
                "If using a proxy, test its listener and try the configured HTTP/Mixed port."
            ]
            message = "HTTPS connection could not be established."
        elif isinstance(exc, httpx.RemoteProtocolError):
            explanation = "The remote server or an intermediary closed the connection or returned an invalid HTTP response."
            causes = ["A proxy or gateway may be incompatible with the request.", "The upstream service may have reset the connection.", "A network security device may be interrupting HTTPS."]
            actions = [
                "Retry once to rule out a transient interruption.",
                "Check proxy and gateway logs or routing mode.",
                "Compare with another permitted network path."
            ]
            message = "Remote server or gateway returned an invalid response."
        else:
            explanation = "The HTTPS request failed before a usable HTTP response was received."
            causes = ["A network, DNS, TLS, firewall, or proxy error interrupted the request."]
            actions = [
                "Review the DNS and TCP stages above.",
                "Check the firewall, VPN/TUN, and proxy configuration.",
                "Retry with --timeout 15 and compare direct versus proxy mode where permitted."
            ]
            message = "HTTPS connection failed."
        steps.append(_step("https", False, message, start, explanation, causes, actions))
        report["advice"] = explanation
        report["recommended_actions"] = actions

    return report
