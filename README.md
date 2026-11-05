# AI NetDoctor

[简体中文](README.md) | [English](README_EN.md)

AI NetDoctor 是一款轻量级 Python 命令行工具，用于诊断访问 AI API 时遇到的网络连接问题。当前支持 OpenAI、Claude 和 Gemini，可检查 DNS 解析、TCP 连接、HTTPS 请求以及 HTTP 代理连通性，并通过终端或 JSON 输出诊断结果。

> 本工具只检查网络层连通性和 HTTP 响应，不验证 API Key、账户额度、权限或模型实际调用能力。

## 快速开始（Windows / PowerShell）

安装 Python 3.10 或更高版本，解压后进入能看到 `pyproject.toml` 的 `ai-netdoctor` 目录：

```powershell
py -3 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -e .
.\\.venv\\Scripts\\ai-netdoctor.exe check openai
.\\.venv\\Scripts\\ai-netdoctor.exe check openai --proxy http://127.0.0.1:7897
.\\.venv\\Scripts\\ai-netdoctor.exe check --all --proxy http://127.0.0.1:7897
.\\.venv\\Scripts\\ai-netdoctor.exe check gemini --json
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
```

安装过程需要下载 HTTPX 及其依赖。代理端口请替换为自己 HTTP/Mixed 代理的实际端口。
无需激活环境，也可用 `.\\.venv\\Scripts\\python.exe -m ai_netdoctor check openai`。

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/ai-netdoctor check openai
.venv/bin/python -m unittest discover -s tests -v
```

## 命令

```text
ai-netdoctor --version
ai-netdoctor check {openai,claude,gemini} [--proxy URL] [--timeout SECONDS] [--json]
ai-netdoctor check --all [--proxy URL] [--timeout SECONDS] [--json]
```

默认超时 5 秒。 `--all` 顺序检查三个服务。退出码：0 表示所有目标均收到 HTTP 响应（407 除外），1 表示至少一个目标的可达性未确认，2 表示参数错误，130 表示用户中断。
JSON 始终使用包含 `version` 和 `results` 数组的对象，便于脚本消费。

## 如何理解结果

- 直连模式：DNS / TCP 检查目标域名和 443 端口。
- 代理模式：DNS / TCP 检查代理地址；HTTPS 通过代理向目标发出请求。
- HTTPS 默认校验证书，使用 GET、不跟随重定向、不下载正文，不进行模型推理。
- 401 / 403：已收到 HTTP 响应，但可能缺少认证、权限或被访问策略拦截。
- 429：已收到 HTTP 响应，需要核对限流或额度。
- 5xx：已收到服务或网关错误。收到响应不代表服务健康。
- 407 或代理 CONNECT 错误：检查代理认证或隧道设置，目标 API 可达性未确认。
- 各阶段独立观察；短暂 DNS/TCP 失败后 HTTPS 仍可能成功。
- 中间网关也可能返回响应，因此本工具不会将 HTTP 响应等同于供应商 API 调用成功。

默认显式关闭环境变量读取（`trust_env=False`），包括 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY` 和 HTTPX 的证书环境变量。需要代理时传入 `--proxy`。
系统路由、VPN/TUN 和透明代理仍可能影响连接。此 MVP 不支持 SOCKS 或自定义 CA 选项。
企业网络如有证书拦截，需要自行配置可信证书的后续扩展，不应关闭证书验证。

超时是 DNS 等待、TCP 阶段与 HTTP 各操作的限制，并非整条命令的绝对总时限。
系统原生 DNS 解析线程无法安全强制终止；极端情况下即使报告 DNS 超时，进程退出仍可能等待解析器。

本程序不读取 API Key。代理 URL 可带用户名和密码，但输出会移除二者，异常也不会原样写入报告。
报告仍含域名、解析 IP、代理地址和时间；公开前请检查是否需要脱敏。
命令行中的代理凭证可能留在终端历史中。

HTTPX 参考：[代理参数](https://www.python-httpx.org/advanced/proxies/)、[环境变量与 trust_env](https://www.python-httpx.org/environment_variables/)。

## 项目结构

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

## 发布版本

项目代码托管在 GitHub。准备发布新版本时：

1. 确认 GitHub Actions 中的测试全部通过。
2. 打开仓库的 [Releases](https://github.com/x549d/ai-netdoctor/releases) 页面，选择 **Draft a new release**。
3. 创建或选择版本标签（例如 `v0.1.0`），目标分支选择 `main`。
4. 填写版本说明，然后选择 **Publish release**。

可选构建 wheel：

```sh
python -m pip wheel . --no-deps --wheel-dir dist
```

## 验证范围

包含 11 项离线模拟测试，覆盖 HTTP 状态语义、DNS/TCP/超时/代理/TLS 错误、凭证脱敏、参数和 JSON 输出。
真实公网连通性取决于使用者网络环境，需自行运行诊断。

## License

MIT，见 [LICENSE](LICENSE)。

## 诊断结果详解与处理方法

每个阶段都会输出 **Explanation（结果解释）**、**Possible cause（可能原因）** 和 **Suggested action（建议操作）**。DNS/TCP 与 HTTPS 是独立观察；即使前两项失败，程序仍会单独尝试 HTTPS。

### DNS：域名解析
- **PASS — Resolved**：当前检查的主机名已解析为 IP。直连模式检查 API 域名；代理模式检查代理主机名。
- **FAIL — DNS lookup timed out**：DNS 未在等待时间内返回。可能是 DNS 服务器不可用、VPN/防火墙干扰或网络暂时异常。检查网络和 DNS；Windows 可运行 `ipconfig /flushdns`，再用 `nslookup <hostname>` 测试，并尝试 `--timeout 15`。
- **FAIL — DNS lookup failed**：系统无法解析主机名。检查域名/代理地址拼写和 DNS 过滤策略；用 `nslookup <hostname>` 查看结果。

### TCP：端口连接
- **PASS — TCP connection established**：到检查主机和端口的 TCP 握手成功；不代表 HTTPS、认证或模型调用成功。
- **FAIL — TCP connection failed or timed out**：DNS 有结果但 TCP 失败。直连模式检查防火墙、VPN/TUN、路由和目标端口；代理模式检查代理程序是否运行、HTTP/Mixed 端口是否正确，以及本机防火墙。
- **FAIL — TCP not attempted**：DNS 没有返回 IP，先修复 DNS。

Windows 可用以下命令检查端口（替换为报告中的主机和端口）：
```powershell
Test-NetConnection api.openai.com -Port 443
Test-NetConnection 127.0.0.1 -Port 7897
```

### HTTPS：HTTP 状态码与错误
- **2xx**：收到成功 HTTP 响应，但本工具不带 API Key，不能证明认证、额度或模型调用可用。
- **301/302/3xx**：收到重定向，本工具不跟随。检查 API Base URL、代理/网关路径改写；若跳转到登录页，检查网络门户。
- **400**：请求格式或端点不接受探测请求。核对路径、方法、API 版本和参数；本工具发送无认证 GET，端点不接受它不代表所有 API 调用都失败。
- **401**：通常是预期结果，因为探测请求不携带 API Key。若自己的程序也返回 401，检查密钥是否存在/有效及认证 Header。不要把密钥发到公开 Issue 或报告。
- **403**：服务器拒绝访问。检查账户/项目权限、区域或 IP 策略；使用代理/VPN 时核对出口 IP 是否被允许。
- **404**：服务器有响应但探测路径不存在。核对服务商 API Base URL 和版本，并检查代理是否改写路径；这不是 DNS 故障。
- **407**：代理要求身份验证，目标 API 是否可达尚未确认。检查代理认证、协议、地址和端口。Clash HTTP/Mixed 端口通常使用 `http://127.0.0.1:<端口>`，不要把 SOCKS-only 端口当作 HTTP 代理。
- **429**：触发限流或额度策略。查看服务商控制台、重试提示、账单/额度，降低频率后重试。
- **5xx**：服务端或网关错误。查看服务状态页，稍后重试；若只在代理线路出现，检查代理上游和网关。
- **HTTPS timeout**：请求未在超时前完成。检查 DNS/TCP、代理上游和防火墙；尝试 `--timeout 15`，并在网络策略允许时比较直连和代理。
- **Proxy / CONNECT error**：代理连接或 HTTPS 隧道失败。确认代理正在监听、URL 协议与端口正确、认证有效且上游可用。
- **TLS verification / handshake failed**：TLS 握手或证书校验失败。检查系统日期时间、根证书和企业 HTTPS 检查设备；企业 TLS 拦截应配置组织提供的可信 CA。**不要关闭证书验证来绕过问题。**
- **Remote protocol / other HTTPS error**：远端或中间网关可能重置连接或返回无效响应。重试一次，检查代理/网关日志，并在允许时比较其他网络路径。

### 结果解读注意事项
1. 代理模式下，DNS/TCP 检查代理主机和端口；HTTPS 才是经代理请求目标 API。
2. DNS/TCP 失败不必然意味着 HTTPS 失败，各阶段结果独立。
3. HTTP 响应只证明某个端点作出了响应，不证明 API Key、权限、额度或模型推理可用。
4. 报告不含 API Key，但可能包含主机名、解析 IP、代理地址和时间。分享前请脱敏；不要暴露代理凭证。
5. 默认忽略环境变量代理；需要代理时显式传入 `--proxy`。
