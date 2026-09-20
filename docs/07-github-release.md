# GitHub 发布流程

## 1. 本地检查

```powershell
uv sync --extra dev
uv run pytest
uv run python -m compileall -q src tests
git status
```

确保工作区干净，所有测试通过。

## 2. 构建发行包

```powershell
uv build
```

输出：

```text
dist/futures_ai_kb-0.2.6.tar.gz
dist/futures_ai_kb-0.2.6-py3-none-any.whl
```

## 3. 创建源码 ZIP

```powershell
New-Item -ItemType Directory -Force dist | Out-Null
git archive --format=zip --output dist/futures-ai-kb-v0.2.6-source.zip HEAD
```

## 4. 创建 Git 标签

```powershell
git tag -a v0.2.6 -m "Futures AI KB v0.2.6"
git push origin main
git push origin v0.2.6
```

如果远程默认分支是 `master`，将 `main` 替换为 `master`。

## 5. 创建 GitHub Release

```powershell
gh release create v0.2.6 `
  dist/futures_ai_kb-0.2.6.tar.gz `
  dist/futures_ai_kb-0.2.6-py3-none-any.whl `
  dist/futures-ai-kb-v0.2.6-source.zip `
  --title "Futures AI KB v0.2.6" `
  --notes-file CHANGELOG.md
```

## 6. 发布前检查

- README 链接可访问。
- License 正确。
- CI 全部通过。
- 没有提交 `data/`、`.env`、Cookie、API Key 或真实交易数据。
- Release 包含 wheel、sdist 和源码 ZIP。
- 版本号与 Git tag 一致。
## 一键构建

提交全部改动并确保测试通过后，可以运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Version 0.2.6
```

脚本会依次执行测试、编译检查、构建 wheel/sdist，并生成源码 ZIP。
