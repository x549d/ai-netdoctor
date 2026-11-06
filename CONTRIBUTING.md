# Contributing

欢迎提交真实复现步骤、问题和改进。提交 Issue 前请记录系统、Python 版本、
工具版本和经过脱敏的诊断结果。不要上传 API Key、代理密码、.env 或私人配置。

开发安装：`python -m pip install -e .`

离线测试：`python -m unittest discover -s tests -v`

新增网络行为需要模拟测试。测试不得依赖公网、账户凭证或付费调用。

## Review and merge

提交 PR 时写明问题、修改效果和验证结果。维护者确认三平台 CI 全部通过，检查 CLI 退出码、JSON 兼容性以及凭证脱敏。打包相关改动还需通过 Package and publish 中的构建和安装后测试。有独立审查者时，合并前请其审查。维护者处理明确的审查意见后再合并。

Describe the problem, user-visible change, and verification in the PR. Wait for the three-platform CI matrix. Check CLI exit codes, JSON compatibility, and credential redaction. Packaging changes also require the build and installed-wheel tests in Package and publish. Request independent review when a reviewer is available and resolve actionable findings before merging.

## Triage and maintenance

- Classify reports by DNS, TCP, TLS, HTTP, proxy, packaging, or docs. Record the tool version, connection mode, and first failing stage. Ask for a minimal, redacted reproduction when more detail is needed.
- If using Codex to summarize an issue or CI failure, pass only reviewed excerpts or synthetic data. Keep private advisories, credentials, private addresses, and raw diagnostic reports out of model input. Review proposed labels, replies, tests, or fixes before applying them.
- For GitHub automatic PR review, connect this repository in [Codex code review settings](https://chatgpt.com/settings/code-review) and enable automatic reviews for the repository. Codex follows the rules in [AGENTS.md](AGENTS.md).

## Release checklist

1. Align `pyproject.toml`, `src/ai_netdoctor/__init__.py`, and `CHANGELOG.md`. Review the user-visible changes and align both READMEs.
2. Merge the release PR after all CI and package checks pass. Wait for CI on the merged commit.
3. Run **Package and publish** on `main` with **Publish** unchecked to build and verify the artifacts. Check the installed CLI version and the distribution metadata.
4. Once the PyPI Trusted Publisher is configured for `x549d/ai-netdoctor`, `publish.yml`, and the `pypi` environment, run the workflow with **Publish** checked on the verified `main` commit. Verify the PyPI version and install from a clean environment.
5. Use the checked wheel and the reviewed changelog for the GitHub release. Tag the verified commit and preserve previous releases.
