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
