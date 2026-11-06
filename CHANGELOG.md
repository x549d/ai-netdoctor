# Changelog

## Unreleased

- HTTP 429 诊断在终端和 JSON 报告中显示通过校验的 `Retry-After`，并在没有可用提示时给出重试建议。

## v0.1.0

- 首次发布 AI NetDoctor 命令行工具，支持单独或依次检查 OpenAI、Claude 和 Gemini API 的 DNS、TCP 和 HTTPS 连通性。
- 支持直连和显式指定 HTTP(S) 代理，默认忽略环境变量中的代理设置。
- 提供终端和 JSON 报告，包含分阶段耗时、HTTP 状态和排查建议。
- 探测无需 API Key，报告会隐藏代理凭证，探测过程不读取响应正文。
