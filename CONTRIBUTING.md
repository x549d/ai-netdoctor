# Contributing

欢迎提交真实复现步骤、问题和改进。提交 Issue 前请记录系统、Python 版本、
工具版本和经过脱敏的诊断结果。不要上传 API Key、代理密码、.env 或私人配置。

开发安装：`python -m pip install -e .`

离线测试：`python -m unittest discover -s tests -v`

新增网络行为需要模拟测试。测试不得依赖公网、账户凭证或付费调用。
提交 PR 时写明问题、修改效果和验证结果。
