# Changelog

## v0.1.2

- Python 包使用 SPDX `MIT` 许可证元数据并附带许可证文件，补充仓库、Issue 和更新日志链接。
- 增加发布打包检查、私密漏洞报告入口、试用反馈表单和 PR 审查流程。

## v0.1.1

- 在子进程中执行系统 DNS 检查，超时后终止并回收子进程。HTTPS 仍独立执行，其内部 DNS 查询不受 DNS 阶段超时控制。
- HTTP 429 和 503 的终端与 JSON 报告支持单个有效的 `Retry-After` 值。缺失或无效时给出重试建议。
- JSON 增加 `http_response_received`、`network_reachable` 和 `api_access_verified`，分别描述收到响应、网络可达和 API 访问验证情况。旧字段和 CLI 退出码保持兼容。
- CI 使用 Node.js 24 版 Actions，在 Linux、Windows 和 macOS 上测试 Python 3.10–3.13 并构建 wheel。

## v0.1.0

- 首次发布 AI NetDoctor 命令行工具，支持单独或依次检查 OpenAI、Claude 和 Gemini API 的 DNS、TCP 和 HTTPS 连通性。
- 支持直连和显式指定 HTTP(S) 代理，默认忽略环境变量中的代理设置。
- 提供终端和 JSON 报告，包含分阶段耗时、HTTP 状态和排查建议。
- 探测无需 API Key，报告会隐藏代理凭证，探测过程不读取响应正文。
