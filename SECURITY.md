# Security Policy

## Supported Versions

当前支持 `0.1.x`。

## Reporting a Vulnerability

请通过 GitHub Security Advisory 私下报告安全问题，不要公开提交包含凭据、交易账户信息或可复现利用细节的 Issue。

## Deployment Safety

- 默认仅监听 `127.0.0.1`。
- 暴露到网络前必须启用 `FUTURES_KB_API_KEY` 或上游认证。
- MCP Streamable HTTP 应置于可信网络或认证网关之后。
- 爬虫配置属于受信任本地文件，不应允许远程用户修改。
- 不要提交 Cookie、API Key、数据库密码和交易账户凭据。
- 不要把数据库文件、原始爬虫数据或真实报告提交到 Git。
- 财务分析结果需要人工复核，不构成投资建议。
