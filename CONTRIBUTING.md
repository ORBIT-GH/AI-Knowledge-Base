# Contributing

感谢你参与 Futures AI KB。

## 开发环境

```powershell
uv sync --extra dev
uv run pytest
```

## 提交前检查

```powershell
uv run pytest
uv run python -m compileall -q src tests
```

## 代码约定

- 数据计算必须使用确定性代码，不依赖模型算术。
- 原始数据不得直接返回给 OpenClaw。
- MCP 工具输出必须有 token 上限。
- 新增数据写入必须支持幂等 upsert。
- 往期报告不得自动加入日报上下文。
- 新增功能必须同时添加测试和 Markdown 流程说明。

## 提交信息

推荐使用：

```text
feat: add new capability
fix: correct a bug
docs: update documentation
test: add or update tests
build: change packaging or dependencies
ci: change workflows
```

## Pull Request

Pull Request 应说明：

1. 修改目的。
2. 主要实现方式。
3. 数据流或接口是否变化。
4. 已运行的测试。
5. 是否涉及数据库迁移。
