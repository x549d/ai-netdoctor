# AI NetDoctor v0.1.0

一个小型 Python 命令行工具，用于排查 AI API 的 DNS、TCP、HTTPS 和 HTTP 代理连接问题。
支持 OpenAI、Claude、Gemini，无需 API Key，无前端、数据库或云服务。

> 本包依据原对话的项目结构重新创建。检测网络响应，不验证 API Key、账户额度或模型可调用性。

## 快速开始（Windows / PowerShell）

安装 Python 3.10 或更高版本，解压后进入能看到 `pyproject.toml` 的 `ai-netdoctor` 目录：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\ai-netdoctor.exe check openai
.\.venv\Scripts\ai-netdoctor.exe check openai --proxy http://127.0.0.1:7897
.\.venv\Scripts\ai-netdoctor.exe check --all --proxy http://127.0.0.1:7897
.\.venv\Scripts\ai-netdoctor.exe check gemini --json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

安装过程需要下载 HTTPX 及其依赖。代理端口请替换为自己 HTTP/Mixed 代理的实际端口。
无需激活环境，也可用 `.\.venv\Scripts\python.exe -m ai_netdoctor check openai`。

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

默认超时 5 秒。`--all` 顺序检查三个服务。退出码：0 表示所有目标均收到 HTTP 响应
（407 除外），1 表示至少一个目标的可达性未确认，2 表示参数错误，130 表示用户中断。
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

默认显式关闭环境变量读取（`trust_env=False`），包括 `HTTP_PROXY`、`HTTPS_PROXY`、
`ALL_PROXY`、`NO_PROXY` 和 HTTPX 的证书环境变量。需要代理时传入 `--proxy`。
系统路由、VPN/TUN 和透明代理仍可能影响连接。此 MVP 不支持 SOCKS 或自定义 CA 选项。
企业网络如有证书拦截，需要自行配置可信证书的后续扩展，不应关闭证书验证。

超时是 DNS 等待、TCP 阶段与 HTTP 各操作的限制，并非整条命令的绝对总时限。
系统原生 DNS 解析线程无法安全强制终止；极端情况下即使报告 DNS 超时，进程退出仍可能等待解析器。

本程序不读取 API Key。代理 URL 可带用户名和密码，但输出会移除二者，异常也不会原样写入报告。
报告仍含域名、解析 IP、代理地址和时间；公开前请检查是否需要脱敏。
命令行中的代理凭证可能留在终端历史中。

HTTPX 参考：[代理参数](https://www.python-httpx.org/advanced/proxies/)、
[环境变量与 trust_env](https://www.python-httpx.org/environment_variables/)。

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
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
└── pyproject.toml
```

## GitHub 发布

在 GitHub 创建名为 `ai-netdoctor` 的公开空仓库，然后在项目根目录执行：

```sh
git init
git branch -M main
git add .
git commit -m "feat: initial MVP release"
git remote add origin https://github.com/YOUR_USERNAME/ai-netdoctor.git
git push -u origin main
```

将 `YOUR_USERNAME` 替换为自己的用户名。查看 Actions 测试结果，
然后在 Releases 中使用 `v0.1.0` 标签发布版本。此压缩包未代为发布到 GitHub 或 PyPI。

可选构建 wheel：

```sh
python -m pip wheel . --no-deps --wheel-dir dist
```

## 开源申请准备

- 公开仓库、README、MIT License、可运行版本及测试记录。
- 维护者身份、真实提交、Issue / PR 和发布记录。
- 实际用户反馈、真实使用数据及工具的社区价值说明。
- 简短项目介绍及后续维护计划。

这些是准备材料，不代表申请资格或通过保证；提交时请核对官方申请页面的最新要求。

## 验证范围

包含 11 项离线模拟测试，覆盖 HTTP 状态语义、DNS/TCP/超时/代理/TLS 错误、
凭证脱敏、参数和 JSON 输出。真实公网连通性取决于使用者网络环境，需自行运行诊断。

## License

MIT，见 LICENSE。
