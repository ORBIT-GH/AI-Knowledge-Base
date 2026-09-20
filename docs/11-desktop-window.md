# 原生桌面窗口

AI Knowledge Base 提供独立的 Windows 桌面窗口，不依赖浏览器。

## 启动源码版本

```powershell
uv sync --extra dev --extra desktop
uv run futures-kb-desktop
```

## 构建单文件 EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
```

输出：

```text
dist\desktop\AIKnowledgeBase.exe
```

## 窗口功能

### 合约管理

- 显示实际主力、主力日期、当前覆盖和可用合约数。
- 选择固定合约并保存到 FuturesIntelTool config。
- 一键恢复自动主力。
- 手动刷新 FuturesIntelTool。

### 日报概览

- 输入交易日。
- 直接调用 `daily_report_context`。
- 显示当前兼容日报数据包。

### 往期报告

- 列出 FuturesIntelTool 源报告和 OpenClaw 最终报告。
- 选择报告后按需读取正文。
- 不会自动把全部报告加载进 OpenClaw 上下文。

## 默认数据后端

EXE 启动时优先读取：

```text
%LOCALAPPDATA%\FuturesIntelTool\config\default.json
```

如果环境变量已设置，优先使用环境变量。

## 图标

桌面程序图标位于：

```text
src\futures_kb\resources\ai-knowledge.ico
```

重新生成图标：

```powershell
uv sync --extra dev --extra desktop
uv run python scripts\generate_icon.py
```

PyInstaller 构建时会把图标写入 EXE，并加载到窗口标题栏。
