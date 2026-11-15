# AI NetDoctor

[简体中文](README.md) | [English](README_EN.md)

AI NetDoctor 是一款轻量级 Python 命令行工具，用于排查访问 OpenAI、Claude 和 Gemini API 时的网络连接问题。它检查 DNS 解析、TCP 端口连接和 HTTPS 响应，支持直连或显式指定 HTTP(S) 代理，并在终端显示逐项解释和处理建议，也可输出 JSON 报告。

> 无需 API Key。本工具只检查网络连通性和 HTTP 响应，不验证密钥、账户额度、权限或模型调用是否成功。

## 功能与检查范围

- 单独检查一个服务，或依次检查全部三个服务。
- 分别报告 DNS、TCP、HTTPS 阶段的结果和耗时，并为异常提供可能原因与建议操作。
- 检查 HTTP(S) 代理连接及 HTTPS CONNECT 隧道；报告中隐藏代理用户名和密码。
- 输出终端报告或结构化 JSON，便于保存和在脚本中读取。

| 命令中的服务名 | 固定 HTTPS 探测地址 |
| --- | --- |
| `openai` | `https://api.openai.com/v1/models` |
| `claude` | `https://api.anthropic.com/v1/models` |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/models` |

直连时，DNS/TCP 检查目标 API 域名和 443 端口。使用代理时，DNS/TCP 检查代理主机和端口，HTTPS 再通过代理请求目标 API。HTTPS 使用不带 API Key 的 GET 请求，校验证书，不跟随重定向，也不读取响应正文。

## 安装与快速开始

使用 Python 3.10 或更高版本，从 [PyPI](https://pypi.org/project/ai-netdoctor/) 安装后即可运行 CLI。

```bash
python -m pip install ai-netdoctor
ai-netdoctor check openai
```

如果已安装 pipx，也可以运行 `pipx install ai-netdoctor`，让 CLI 使用独立的环境。[GitHub Releases](https://github.com/x549d/ai-netdoctor/releases/latest) 提供 wheel 下载。

需要 **Python 3.10 或更高版本**。CI 在 Linux、Windows 和 macOS 上覆盖 Python 3.10–3.13。在 [仓库页面](https://github.com/x549d/ai-netdoctor) 选择 **Code → Download ZIP** 并解压，或获取仓库副本，然后进入包含 `pyproject.toml` 的目录。安装需要联网下载构建依赖、HTTPX 及其依赖。

### Windows / PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\ai-netdoctor.exe check openai
```

无需激活虚拟环境。也可使用模块方式运行：

```powershell
.\.venv\Scripts\python.exe -m ai_netdoctor check openai
```

### macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/ai-netdoctor check openai
```

若系统提示缺少 venv 或 pip，请先通过系统的软件包管理器安装对应的 Python 组件。

## 命令与常用操作

以下示例中的 `ai-netdoctor`，请替换为上方对应系统的虚拟环境可执行文件路径；已激活虚拟环境时可直接使用命令名。

```text
ai-netdoctor --help
ai-netdoctor --version
ai-netdoctor check --help
ai-netdoctor check {openai,claude,gemini} [--proxy URL] [--timeout SECONDS] [--json]
ai-netdoctor check --all [--proxy URL] [--timeout SECONDS] [--json]
```

必须选择一个服务或 `--all`，两者不能同时使用。

| 参数 | 用法 |
| --- | --- |
| `--all` | 按 OpenAI、Claude、Gemini 的顺序逐一检查。 |
| `--proxy URL` | 显式使用 `http://` 或 `https://` 代理地址。使用代理实际的主机和 HTTP/Mixed 端口；不支持 SOCKS。 |
| `--timeout SECONDS` | 设置 DNS 等待、TCP 阶段及 HTTP 各操作的超时，默认 5 秒；必须是有限的正数。 |
| `--json` | 输出一个 JSON 对象，替代终端文本报告。 |

```sh
ai-netdoctor check claude
ai-netdoctor check openai --proxy http://127.0.0.1:7897
ai-netdoctor check --all --proxy http://127.0.0.1:7897 --timeout 15
ai-netdoctor check gemini --json
ai-netdoctor check --all --json > report.json
```

`7897` 只是示例，请替换为代理程序的实际 HTTP/Mixed 端口。Clash 等程序的 HTTP/Mixed 监听端口通常使用 `http://127.0.0.1:<端口>`，即使目标 API 使用 HTTPS 也是如此。

### JSON 报告与退出码

JSON 顶层包含 `version` 和 `results` 数组，即使只检查一个服务也使用相同结构。每个结果包含：

- 目标与检查范围：`provider`、`target`、`url`、`proxy`、`probe_scope`、`probe_host`、`probe_port`。
- UTC 时间戳：`timestamp`。
- 分阶段结果：`steps`，每项包含 `stage`、`ok`、`message`、`elapsed_ms`、`explanation`、`possible_causes`、`recommended_actions`。
- `http_response_received` 表示 HTTPS 探测是否取得 HTTP 响应，包括客户端返回的 407。没有响应时，`http_status` 为 `null`。如果代理在建立 CONNECT 隧道时拒绝请求，HTTP 客户端可能只报告代理错误。
- `network_reachable` 在 HTTPS 探测取得非 407 响应时为 `true`，响应也可能来自中间网关。旧字段 `reachable` 保持相同的含义和值。
- `api_access_verified` 在当前无凭证探测中始终为 `false`，包括收到 2xx 时。验证实际 API 访问需要应用发起带凭证的请求。
- `result`、`advice` 和 `recommended_actions` 提供总体判断与建议。
- HTTP 429 和 503 可附带 `retry_after` 字符串。只有单个有效值才会显示，格式为 1 至 10 位 ASCII 数字表示的等待秒数（如 `"120"`），或 HTTP 日期。

| 退出码 | 含义 |
| --- | --- |
| 0 | 所有目标都收到 HTTP 响应，且状态码不是 407；包括 4xx、5xx，不代表 API 调用成功。 |
| 1 | 至少一个目标未收到 HTTP 响应，或收到 407，目标可达性未确认。 |
| 2 | 参数错误；按错误提示检查服务名、代理 URL、超时值等。 |
| 130 | 用户中断操作。 |

## 诊断结果解释与逐项处理方法

终端报告使用 **Explanation（结果解释）**、**Possible cause（可能原因）** 和 **Suggested action（建议操作）** 展示相应信息；正常阶段可能没有原因或操作建议。

DNS/TCP 与 HTTPS 是独立观察。即使前两项失败，工具仍会单独尝试 HTTPS。瞬时故障可能导致结果不同，应结合最终 `Result` 或 JSON 中的 `network_reachable` 判断。

### DNS：域名解析

| 结果 | 解释与可能原因 | 处理方法 |
| --- | --- | --- |
| **PASS — Resolved** | 检查的主机名已解析为一个或多个 IP；代理模式下是代理主机。 | 继续查看 TCP 和 HTTPS 结果。 |
| **FAIL — No addresses returned** | 解析器完成查询，但未返回可用 IP，可能缺少 DNS 记录或返回空结果。 | 核对主机名，运行 `nslookup <hostname>` 检查解析结果。 |
| **FAIL — DNS lookup timed out** | 解析器未在等待时间内返回；DNS 服务器可能缓慢或不可达，VPN/防火墙也可能干扰。 | 检查网络和 DNS；Windows 可尝试 `ipconfig /flushdns`，再用 `nslookup <hostname>` 检查；使用 `--timeout 15` 重试。 |
| **FAIL — DNS lookup failed** | 主机名不存在、临时解析失败、DNS 过滤或本机解析配置异常。 | 核对域名和代理地址拼写；检查 DNS/VPN 设置，稍后重试，必要时在获准的其他网络比较解析结果。 |

将 `<hostname>` 替换为报告中的 `probe_host`；代理模式下应检查代理主机名。

### TCP：端口连接

| 结果 | 解释与可能原因 | 处理方法 |
| --- | --- | --- |
| **PASS — TCP connection established** | 到检查主机和端口的 TCP 握手成功；不代表 HTTPS 或 API 认证成功。 | 继续查看 HTTPS。 |
| **FAIL — TCP connection failed or timed out** | DNS 返回了地址，但 TCP 连接失败；可能被防火墙/路由阻止、目标不可达，或代理未启动、端口错误。 | 直连时检查防火墙、VPN/TUN、路由和 443 端口；代理模式下确认代理已运行、HTTP/Mixed 端口正确，并检查本机防火墙和代理上游。 |
| **FAIL — TCP not attempted** | DNS 没有提供 IP，无法进行 TCP 检查。 | 先按 DNS 阶段的建议处理，再重试。 |

Windows 可检查端口；将主机和端口替换为报告中的值：

```powershell
Test-NetConnection api.openai.com -Port 443
Test-NetConnection 127.0.0.1 -Port 7897
```

### HTTPS：HTTP 状态码

**HTTPS 阶段的 PASS 只表示收到了 HTTP 响应。** 即使状态是 407，该阶段也可能显示 PASS，但总体结果仍会将目标可达性标记为未确认，并返回退出码 1。

| 状态 | 解释与可能原因 | 处理方法 |
| --- | --- | --- |
| **2xx** | 收到成功 HTTP 响应；无认证探测不验证密钥、权限、额度或模型可用性。 | 若应用仍失败，检查应用自身的 API Key、认证 Header、项目权限、模型和请求格式。 |
| **3xx（含 301/302）** | 收到重定向，工具不会跟随；可能是路径变化、网关改写或网络登录门户。 | 核对表中的固定探测地址与服务商文档，检查代理/网关改写规则；若跳转到登录页，完成网络接入认证。 |
| **400** | 端点拒绝探测请求，可能不接受无认证 GET，或需要其他参数/Header。 | 对照服务商文档核对方法、路径、版本和参数；若应用也失败，检查应用请求。单次探测被拒不代表所有 API 调用不可用。 |
| **401** | 通常是预期结果，因为工具不携带 API Key。 | 若只有探测返回 401，说明某个 HTTPS 端点已响应；若应用也返回 401，检查密钥是否有效及认证 Header 是否正确。不要公开密钥。 |
| **403** | 服务器或网关拒绝访问；可能受 IP、区域、账户/项目权限或防火墙策略限制。 | 检查服务商访问政策、应用权限及代理/VPN 出口 IP；在政策允许时比较其他网络路径。 |
| **404** | 服务器响应了，但探测路径不存在；可能是 API 版本变化或代理路径改写。 | 比较固定探测地址与服务商当前文档，检查网关改写。若应用请求正常，可能只是探测路径不受支持；这不是 DNS 故障。 |
| **407** | 代理要求认证；目标 API 可达性未确认。 | 核对代理认证、协议、主机和端口，确认代理监听与上游连接正常。需要凭证时通过 `--proxy` URL 提供，并注意命令历史中的泄露风险；不要使用 SOCKS-only 端口。 |
| **429** | 服务或网关触发限流或额度策略。 | 如果终端报告显示 `Retry-After`，按提示等待；没有可用提示时，降低请求频率或并发并稍后重试。检查服务商控制台的限流、额度和账单，或检查网关策略。如果应用也收到 429，请查看应用自身响应中的重试提示。 |
| **其他 4xx** | 端点拒绝请求，可能需要不同的方法、参数、Header 或访问策略。 | 查阅服务商文档；若应用也失败，检查应用的请求方法、路径、认证和参数。 |
| **503** | 服务或网关暂时无法处理请求。 | 如果报告显示 `Retry-After`，按提示等待；否则查看服务状态页并稍后重试。 |
| **其他 5xx** | 服务端或中间网关错误；收到响应不代表服务健康。 | 查看服务状态页并稍后重试；若只有代理线路失败，检查代理上游和网关。 |
| **其他 HTTP 状态** | 某个 HTTP 端点已响应，状态可能具有服务商特定含义。 | 查阅对应状态说明，并结合应用响应检查认证、权限和请求格式。 |

探测地址是固定的，当前命令不能修改 API Base URL、请求方法或 Header。上述核对用于定位问题，并指导检查应用或代理配置。

### HTTPS：连接与协议错误

| 结果 | 解释与可能原因 | 处理方法 |
| --- | --- | --- |
| **HTTPS request timed out** | HTTP 操作超时；目标或代理缓慢、不可达，或网络设备丢弃/延迟流量。 | 结合 DNS/TCP 结果检查网络、代理监听和上游；尝试 `--timeout 15`，并在政策允许时比较直连与代理。 |
| **Proxy connection or CONNECT tunnel failed** | 代理连接或 HTTPS 隧道建立失败；可能是端口、协议、认证或上游配置错误。 | 确认代理运行且监听正确的 HTTP/Mixed 端口，核对 URL 协议和认证，检查代理路由及上游；用端口检查命令验证监听。 |
| **TLS verification or handshake failed** | TLS 握手或证书校验失败；可能是系统时间错误、证书链不可信或企业 HTTPS 检查。 | 核对日期、时间和时区，检查证书链；企业网络请向管理员核实组织 CA 是否受当前 Python/HTTPX 信任配置支持，或使用获准且兼容的网络路径。本工具没有自定义 CA 选项，且忽略证书环境变量；不要关闭证书验证。 |
| **HTTPS connection could not be established** | HTTPS 客户端无法连接目标或代理；可能是路由阻断、代理不可用或远端拒绝连接。 | 查看 DNS/TCP，检查防火墙、VPN/TUN、代理监听端口和上游路由。 |
| **Remote server or gateway returned an invalid response** | 远端或中间设备关闭连接，或返回无效 HTTP 响应。 | 重试一次排除瞬时故障，检查代理/网关日志和路由模式，并在允许时比较其他网络。 |
| **HTTPS connection failed** | 收到有效 HTTP 响应前请求失败，可能涉及网络、DNS、TLS、防火墙或代理。 | 结合前面阶段定位问题，检查相关配置；尝试 `--timeout 15` 并在允许时比较直连与代理。 |

## 隐私与安全

- 不读取 API Key，不发送模型推理请求，也不读取 HTTPS 响应正文。探测仍会连接目标服务或代理，对方可见连接 IP 和请求元数据。
- 仅在 HTTP 429 和 503 报告中显示通过校验的 `Retry-After`。缺失、重复或无效的值会省略，其他响应头也不会写入报告。
- 代理 URL 可包含用户名和密码；终端和 JSON 报告会移除它们，异常不会原样写入报告。命令行凭证仍可能出现在终端历史或本机进程参数中。
- 报告包含域名、解析 IP、代理地址及时间戳。保存或分享前检查并按需脱敏，不要添加密钥或代理凭证。
- HTTPS 保持证书验证。遇到 TLS 问题时检查信任配置或联系网络管理员，不要通过关闭验证绕过问题。

## 限制与注意事项

- HTTP 响应只表明某个端点响应，不证明供应商身份、API 健康、密钥、权限、额度或模型调用能力；中间网关也可能响应。
- 默认忽略环境变量代理和 HTTPX 的证书环境变量（`trust_env=False`），包括 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`。需要代理时必须显式传入 `--proxy`；VPN/TUN、系统路由和透明代理仍可能影响连接。
- 仅支持固定的三个服务地址及 HTTP(S) 代理，不支持 SOCKS、自定义目标 URL 或自定义 CA 命令选项。
- 超时分别应用于 DNS 等待、TCP 阶段及 HTTP 各操作，不是整条命令的绝对总时限；`--all` 顺序执行，耗时会累加。
- DNS 阶段在独立子进程中使用系统解析器，超时后终止并回收子进程。启动与清理子进程可能增加少量耗时。HTTPS 会独立连接，其内部的系统 DNS 查询仍可能超出设定时限。
- 结果反映运行时的网络状况；遇到间歇性故障可在允许的网络路径上重试比较。

## 参与项目

- [贡献指南](CONTRIBUTING.md)介绍本地测试和 PR 流程。
- [社区行为准则](CODE_OF_CONDUCT.md)说明社区规范和违规举报流程。
- [安全政策](SECURITY.md)说明如何私下报告漏洞。
- [故障报告](https://github.com/x549d/ai-netdoctor/issues/new?template=bug.yml)用于提交可复现的问题。
- [功能建议](https://github.com/x549d/ai-netdoctor/issues/new?template=feature_request.yml)用于说明需求、使用场景和预期效果。
- [试用反馈](https://github.com/x549d/ai-netdoctor/issues/new?template=field-feedback.yml)用于分享工具在实际排查中是否帮助缩小了问题范围。

## 许可证

本工具采用 [MIT 许可证](LICENSE)，按“原样”提供，不附带任何担保。
