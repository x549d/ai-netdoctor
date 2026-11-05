# AI NetDoctor

[简体中文](README.md) | [English](README_EN.md)

AI NetDoctor is a lightweight Python command-line tool for diagnosing network connectivity issues when accessing AI APIs. It currently supports OpenAI, Claude, and Gemini, and checks DNS resolution, TCP connectivity, HTTPS requests, and HTTP proxy connectivity. Diagnostic results can be displayed in the terminal or exported as JSON.

> This tool checks network-layer connectivity and HTTP responses only. It does not validate API keys, account quotas, permissions, or whether a model request can actually be completed.

## Quick Start (Windows / PowerShell)

Install Python 3.10 or later, extract the project, and open a terminal in the `ai-netdoctor` directory containing `pyproject.toml`:

```powershell
py -3 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -e .
.\\.venv\\Scripts\\ai-netdoctor.exe check openai
.\\.venv\\Scripts\\ai-netdoctor.exe check openai --proxy http://127.0.0.1:7897
.\\.venv\\Scripts\\ai-netdoctor.exe check --all --proxy http://127.0.0.1:7897
.\\.venv\\Scripts\\ai-netdoctor.exe check gemini --json
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
```

Installation downloads HTTPX and its dependencies. Replace the proxy port with the actual HTTP/Mixed port used by your proxy.
You do not need to activate the virtual environment. You can also run `.\\.venv\\Scripts\\python.exe -m ai_netdoctor check openai`.

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/ai-netdoctor check openai
.venv/bin/python -m unittest discover -s tests -v
```

## Commands

```text
ai-netdoctor --version
ai-netdoctor check {openai,claude,gemini} [--proxy URL] [--timeout SECONDS] [--json]
ai-netdoctor check --all [--proxy URL] [--timeout SECONDS] [--json]
```

The default timeout is 5 seconds. `--all` checks the three services sequentially. Exit codes: 0 means all targets returned an HTTP response (except 407); 1 means connectivity could not be confirmed for at least one target; 2 indicates invalid arguments; and 130 indicates user interruption.
JSON output is always an object containing a `version` field and a `results` array, making it suitable for scripts.

## Understanding the Results

- Direct mode: DNS and TCP checks target the destination hostname and port 443.
- Proxy mode: DNS and TCP checks target the proxy; HTTPS requests to the destination are sent through that proxy.
- HTTPS certificate verification is enabled by default. The tool sends GET requests, does not follow redirects, does not download response bodies, and does not perform model inference.
- 401 / 403: An HTTP response was received, but authentication, permissions, or access policies may prevent use.
- 429: An HTTP response was received; check rate limits or account quota.
- 5xx: A server or gateway error was received. Receiving a response does not mean the service is healthy.
- 407 or a proxy CONNECT error: Check proxy authentication or tunnel configuration. Connectivity to the target API has not been confirmed.
- Each stage is observed independently. HTTPS may still succeed after a transient DNS or TCP failure.
- An intermediary gateway may also return a response, so an HTTP response is not treated as proof that the provider API can complete a model request.

Environment-variable loading is explicitly disabled by default (`trust_env=False`), including `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, and HTTPX certificate-related environment variables. Pass `--proxy` when a proxy is required.
System routing, VPN/TUN, and transparent proxies may still affect connectivity. This MVP does not support SOCKS proxies or custom CA options.
For corporate networks that intercept TLS certificates, a future extension may allow a trusted CA to be configured. Certificate verification should not be disabled.

Timeouts apply to DNS waiting, the TCP stage, and individual HTTP operations; they are not a strict total runtime limit for the entire command.
The operating system's native DNS resolver thread cannot be safely force-terminated. In rare cases, the process may still wait for the resolver to finish even after a DNS timeout is reported.

The program does not read API keys. Proxy URLs may contain usernames and passwords, but these credentials are removed from output and are not copied verbatim into exception reports.
Reports still contain hostnames, resolved IP addresses, proxy addresses, and timestamps. Review and redact them as needed before sharing.
Proxy credentials included in command-line arguments may remain in terminal history.

HTTPX references: [Proxy configuration](https://www.python-httpx.org/advanced/proxies/) and [Environment variables and trust_env](https://www.python-httpx.org/environment_variables/).

## Project Structure

```text
ai-netdoctor/
├── src/ai_netdoctor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   └── core.py
├── tests/test_core.py
├── .github/workflows/ci.yml
├── README.md
├── README_EN.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
└── pyproject.toml
```

## Releasing a Version

The project source code is hosted on GitHub. To publish a new release:

1. Confirm that all GitHub Actions checks have passed.
2. Open the repository's [Releases](https://github.com/x549d/ai-netdoctor/releases) page and select **Draft a new release**.
3. Create or select a version tag (for example, `v0.1.0`) and choose `main` as the target branch.
4. Add the release notes and select **Publish release**.

To optionally build a wheel:

```sh
python -m pip wheel . --no-deps --wheel-dir dist
```

## Test Coverage

The project includes 11 offline unit tests covering HTTP status semantics, DNS/TCP/timeouts/proxy/TLS errors, credential redaction, command-line arguments, and JSON output.
Real-world public network connectivity depends on the user's network environment and should be tested by running the diagnostic commands.

## License

MIT. See [LICENSE](LICENSE).
