# AI NetDoctor

[简体中文](README.md) | [English](README_EN.md)

AI NetDoctor is a lightweight Python command-line tool for troubleshooting network connectivity to the OpenAI, Claude, and Gemini APIs. It checks DNS resolution, TCP ports, and HTTPS responses, using a direct connection or an explicitly configured HTTP(S) proxy. It displays explanations and suggested actions in the terminal and can output JSON reports.

> No API key is required. This tool checks network connectivity and HTTP responses only; it does not validate keys, account quotas, permissions, or successful model requests.

## Features and Check Scope

- Check one service or all three services sequentially.
- View independent DNS, TCP, and HTTPS results and timings, with possible causes and suggested actions for problems.
- Check HTTP(S) proxy connections and HTTPS CONNECT tunnels; proxy usernames and passwords are hidden in reports.
- Read terminal reports or structured JSON for saving and scripting.

| Service name in commands | Fixed HTTPS probe URL |
| --- | --- |
| `openai` | `https://api.openai.com/v1/models` |
| `claude` | `https://api.anthropic.com/v1/models` |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/models` |

In direct mode, DNS/TCP checks target the API hostname and port 443. With a proxy, DNS/TCP checks target the proxy host and port, and HTTPS then requests the API through that proxy. HTTPS uses GET without an API key, verifies certificates, does not follow redirects, and does not read response bodies.

## Installation and Quick Start

You need **Python 3.10 or later**. On the [repository page](https://github.com/x549d/ai-netdoctor), choose **Code → Download ZIP** and extract it, or obtain a repository copy. Open a terminal in the directory containing `pyproject.toml`. Installation requires internet access to download build dependencies, HTTPX, and its dependencies.

### Windows / PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\ai-netdoctor.exe check openai
```

You do not need to activate the virtual environment. You can also run the module:

```powershell
.\.venv\Scripts\python.exe -m ai_netdoctor check openai
```

### macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/ai-netdoctor check openai
```

If your system reports that venv or pip is missing, install the corresponding Python components through your system's package manager first.

## Commands and Common Tasks

In the examples below, replace `ai-netdoctor` with the virtual-environment executable path for your system shown above. If the environment is activated, use the command name directly.

```text
ai-netdoctor --help
ai-netdoctor --version
ai-netdoctor check --help
ai-netdoctor check {openai,claude,gemini} [--proxy URL] [--timeout SECONDS] [--json]
ai-netdoctor check --all [--proxy URL] [--timeout SECONDS] [--json]
```

Choose either one service or `--all`; they cannot be used together.

| Option | Usage |
| --- | --- |
| `--all` | Check OpenAI, Claude, and Gemini one at a time, in that order. |
| `--proxy URL` | Explicitly use an `http://` or `https://` proxy URL. Use your proxy's actual host and HTTP/Mixed port; SOCKS is not supported. |
| `--timeout SECONDS` | Set the timeout for DNS waiting, the TCP stage, and individual HTTP operations. Default: 5 seconds; must be a finite positive number. |
| `--json` | Output one JSON object instead of the terminal text report. |

```sh
ai-netdoctor check claude
ai-netdoctor check openai --proxy http://127.0.0.1:7897
ai-netdoctor check --all --proxy http://127.0.0.1:7897 --timeout 15
ai-netdoctor check gemini --json
ai-netdoctor check --all --json > report.json
```

`7897` is only an example; replace it with the proxy application's actual HTTP/Mixed port. HTTP/Mixed listeners in applications such as Clash typically use `http://127.0.0.1:<port>`, even when the target API uses HTTPS.

### JSON Reports and Exit Codes

The JSON object contains `version` and a `results` array, using the same structure even for a single service. Each result includes:

- Target and check scope: `provider`, `target`, `url`, `proxy`, `probe_scope`, `probe_host`, `probe_port`.
- UTC timestamp: `timestamp`.
- Stage results: `steps`, each with `stage`, `ok`, `message`, `elapsed_ms`, `explanation`, `possible_causes`, `recommended_actions`.
- Overall assessment and guidance: `http_status`, `reachable`, `result`, `advice`, `recommended_actions`. If no HTTP response was received, `http_status` is `null`.

| Exit code | Meaning |
| --- | --- |
| 0 | All targets returned an HTTP response other than 407; this includes 4xx and 5xx and does not mean API requests succeeded. |
| 1 | At least one target returned no HTTP response or returned 407; target reachability is not confirmed. |
| 2 | Invalid arguments; follow the error message to check the service name, proxy URL, timeout, or other arguments. |
| 130 | The user interrupted the operation. |

## Diagnostic Results and Step-by-Step Remedies

The terminal report displays **Explanation**, **Possible cause**, and **Suggested action** where applicable; successful stages may have no causes or suggested actions.

DNS/TCP and HTTPS are independent observations. HTTPS is attempted separately even when the first two stages fail. Transient failures can produce different results, so also read the final `Result` or JSON `reachable` value. An intermediary gateway may return the HTTP response; it does not prove the provider API or a model is available.

### DNS: Hostname Resolution

| Result | Explanation and possible causes | What to do |
| --- | --- | --- |
| **PASS — Resolved** | The checked hostname resolved to one or more IP addresses; in proxy mode, this is the proxy host. | Continue to the TCP and HTTPS results. |
| **FAIL — No addresses returned** | The resolver finished but returned no usable IP addresses, possibly because records are missing or the result is empty. | Verify the hostname and run `nslookup <hostname>` to inspect resolution. |
| **FAIL — DNS lookup timed out** | The resolver did not answer within the waiting period; DNS may be slow or unreachable, or a VPN/firewall may interfere. | Check the network and DNS. On Windows, try `ipconfig /flushdns`, then `nslookup <hostname>`; retry with `--timeout 15`. |
| **FAIL — DNS lookup failed** | The hostname may not exist, resolution may have failed temporarily, or DNS filtering/local resolver settings may interfere. | Check the hostname and proxy URL spelling; review DNS/VPN settings, retry later, and compare resolution on another permitted network if needed. |

Replace `<hostname>` with `probe_host` from the report; in proxy mode, check the proxy hostname.

### TCP: Port Connectivity

| Result | Explanation and possible causes | What to do |
| --- | --- | --- |
| **PASS — TCP connection established** | The TCP handshake completed with the checked host and port; this does not prove HTTPS or API authentication works. | Continue to HTTPS. |
| **FAIL — TCP connection failed or timed out** | DNS returned addresses, but TCP failed; a firewall/route may block it, the destination may be unreachable, or the proxy may be stopped or use a different port. | In direct mode, check the firewall, VPN/TUN, routing, and port 443. In proxy mode, confirm the proxy is running on the correct HTTP/Mixed port, then check the local firewall and proxy upstream. |
| **FAIL — TCP not attempted** | DNS provided no IP address, so TCP could not be checked. | Follow the DNS stage's suggested actions first, then retry. |

On Windows, check a port by replacing the host and port with the values from the report:

```powershell
Test-NetConnection api.openai.com -Port 443
Test-NetConnection 127.0.0.1 -Port 7897
```

### HTTPS: HTTP Status Codes

**PASS for the HTTPS stage only means that an HTTP response was received.** Even 407 may show PASS for that stage, while the overall result still marks target reachability as unconfirmed and returns exit code 1.

| Status | Explanation and possible causes | What to do |
| --- | --- | --- |
| **2xx** | A successful HTTP response was received; this unauthenticated probe does not verify keys, permissions, quotas, or model availability. | If your application still fails, check its API key, authentication headers, project permissions, model, and request format. |
| **3xx (including 301/302)** | A redirect was returned and is not followed; the path may have changed, a gateway may rewrite it, or a captive portal may intervene. | Compare the fixed probe URL above with provider documentation and check proxy/gateway rewrite rules. If redirected to a login page, complete network access authentication. |
| **400** | The endpoint rejected the probe, possibly because it does not accept unauthenticated GET or requires other parameters/headers. | Check the method, path, version, and parameters against provider documentation. If your application also fails, inspect its request. A rejected probe does not mean all API requests are unavailable. |
| **401** | Commonly expected because the tool sends no API key. | If only the probe returns 401, an HTTPS endpoint has responded. If your application also returns 401, check its key validity and authentication headers. Never share keys publicly. |
| **403** | The server or gateway refused access, possibly because of IP, regional, account/project permission, or firewall policies. | Check provider access policies, application permissions, and the proxy/VPN egress IP; compare other network paths where policies permit. |
| **404** | The server responded, but the probe path was not found; the API version may have changed or a proxy may have rewritten the path. | Compare the fixed probe URL with current provider documentation and check gateway rewrites. If application requests work, only the probe path may be unsupported; this is not a DNS failure. |
| **407** | The proxy requires authentication; target API reachability is unconfirmed. | Check proxy credentials, scheme, host, and port, and verify the listener and upstream. Supply credentials through the `--proxy` URL if needed, taking care with command-history exposure; do not use a SOCKS-only port. |
| **429** | The service or gateway applied a rate-limit or quota policy. | Check provider dashboard limits, quota, billing, and retry hints in application responses. Reduce frequency/concurrency and wait as advised. If a gateway responded, check its policy too. |
| **Other 4xx** | The endpoint rejected the request and may require different methods, parameters, headers, or access policies. | Consult provider documentation. If your application also fails, check its method, path, authentication, and parameters. |
| **5xx** | The service or an intermediary gateway returned an error; a response does not mean the service is healthy. | Check the service-status page and retry later. If only the proxy route fails, inspect its upstream and gateway. |
| **Other HTTP status** | An HTTP endpoint responded; the status may have a provider-specific meaning. | Consult the status documentation and use your application's response to check authentication, permissions, and request format. |

Probe URLs are fixed; the current command cannot change the API base URL, request method, or headers. These comparisons help locate problems and guide checks of application or proxy configuration.

### HTTPS: Connection and Protocol Errors

| Result | Explanation and possible causes | What to do |
| --- | --- | --- |
| **HTTPS request timed out** | An HTTP operation timed out; the target/proxy may be slow or unreachable, or network devices may drop/delay traffic. | Review DNS/TCP, the network, the proxy listener, and upstream. Try `--timeout 15` and compare direct/proxy routes where policies permit. |
| **Proxy connection or CONNECT tunnel failed** | The proxy connection or HTTPS tunnel failed, possibly because of incorrect ports, schemes, credentials, or upstream configuration. | Confirm the proxy is running on its HTTP/Mixed port, verify the URL scheme and authentication, and check routing/upstream. Use a port check to verify the listener. |
| **TLS verification or handshake failed** | TLS negotiation or certificate verification failed, possibly because of an incorrect clock, an untrusted certificate chain, or corporate HTTPS inspection. | Check date, time, time zone, and the certificate chain. On corporate networks, ask the administrator whether the organization's CA is supported by the current Python/HTTPX trust configuration, or use a permitted compatible network path. This tool has no custom CA option and ignores certificate environment variables; do not disable certificate verification. |
| **HTTPS connection could not be established** | The HTTPS client could not connect to the target or proxy, possibly because of blocked routing, proxy unavailability, or a refused connection. | Review DNS/TCP and check the firewall, VPN/TUN, proxy listener port, and upstream routing. |
| **Remote server or gateway returned an invalid response** | The remote server or an intermediary closed the connection or returned an invalid HTTP response. | Retry once to rule out a transient failure, inspect proxy/gateway logs and routing mode, and compare another network where permitted. |
| **HTTPS connection failed** | The request failed before a usable HTTP response arrived, possibly involving the network, DNS, TLS, firewall, or proxy. | Use the earlier stages to locate the problem and check the relevant settings. Try `--timeout 15` and compare direct/proxy routes where permitted. |

## Privacy and Security

- The tool does not read API keys, send model inference requests, or read HTTPS response bodies. Probes still connect to a target service or proxy, which can see the connection IP and request metadata.
- Proxy URLs can include usernames and passwords; these are removed from terminal and JSON reports, and exceptions are not copied verbatim into reports. Command-line credentials may still appear in terminal history or local process arguments.
- Reports contain hostnames, resolved IPs, proxy addresses, and timestamps. Review and redact them before saving or sharing; do not add keys or proxy credentials.
- HTTPS certificate verification stays enabled. For TLS problems, check trust configuration or contact your network administrator; do not bypass them by disabling verification.

## Limitations and Notes

- An HTTP response only proves that an endpoint responded. It does not establish provider identity, API health, keys, permissions, quotas, or model access; an intermediary gateway may respond.
- Environment proxy variables and HTTPX certificate environment variables are ignored by default (`trust_env=False`), including `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`. Pass `--proxy` explicitly when needed. VPN/TUN, system routing, and transparent proxies can still affect connections.
- Only the three fixed service URLs and HTTP(S) proxies are supported. SOCKS, custom target URLs, and custom CA command options are not supported.
- Timeouts apply separately to DNS waiting, the TCP stage, and individual HTTP operations; they are not an absolute runtime limit for the entire command. `--all` runs sequentially, so durations add up.
- The operating system's native DNS resolver thread cannot be safely force-terminated. In rare cases, process exit may still wait for it after a DNS timeout is reported.
- Results reflect network conditions at the time of the check. For intermittent problems, retry and compare permitted network paths.

## License

This tool is available under the [MIT License](LICENSE) and is provided "as is", without warranty.
