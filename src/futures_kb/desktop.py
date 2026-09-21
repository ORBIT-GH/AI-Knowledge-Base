"""Native Windows desktop control panel for AI Knowledge Base."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import StringVar, Text, Tk, messagebox, ttk
from typing import Any, Callable

from futures_kb.config import Settings
from futures_kb.service import FuturesDataService, create_service


class DesktopApp:
    """Tkinter desktop window backed directly by FuturesDataService."""

    def __init__(self, root: Tk, service: FuturesDataService | None = None) -> None:
        self.root = root
        self.root.title("AI Knowledge 控制台")
        self.root.geometry("1120x760")
        self.root.minsize(920, 620)
        self.service = service or create_service(settings=default_settings())
        self.status_var = StringVar(value="正在初始化...")
        self.symbol_var = StringVar()
        self.contract_var = StringVar()
        self.report_date_var = StringVar(value=date.today().isoformat())
        self.contract_rows: list[dict[str, Any]] = []
        self.report_rows: list[dict[str, Any]] = []
        self._build()
        self.refresh_contracts()

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="AI Knowledge Base", font=("Microsoft YaHei", 16, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.status_var, foreground="#355d8a").pack(side="right")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.contract_tab = ttk.Frame(notebook, padding=12)
        self.context_tab = ttk.Frame(notebook, padding=12)
        self.archive_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.contract_tab, text="合约管理")
        notebook.add(self.context_tab, text="日报概览")
        notebook.add(self.archive_tab, text="往期报告")

        self._build_contract_tab()
        self._build_context_tab()
        self._build_archive_tab()

    def _build_contract_tab(self) -> None:
        columns = ("symbol", "name", "main", "date", "override", "available")
        self.contract_tree = ttk.Treeview(
            self.contract_tab,
            columns=columns,
            show="headings",
            height=12,
        )
        headings = {
            "symbol": "品种",
            "name": "名称",
            "main": "实际主力",
            "date": "主力日期",
            "override": "当前覆盖",
            "available": "可用合约数",
        }
        widths = {"symbol": 80, "name": 120, "main": 120, "date": 120, "override": 120, "available": 100}
        for column in columns:
            self.contract_tree.heading(column, text=headings[column])
            self.contract_tree.column(column, width=widths[column], anchor="center")
        self.contract_tree.pack(fill="both", expand=True)
        self.contract_tree.bind("<<TreeviewSelect>>", self._on_contract_row_selected)

        controls = ttk.LabelFrame(self.contract_tab, text="修改报告合约", padding=12)
        controls.pack(fill="x", pady=(12, 0))
        ttk.Label(controls, text="品种").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.symbol_combo = ttk.Combobox(controls, textvariable=self.symbol_var, width=12, state="readonly")
        self.symbol_combo.grid(row=0, column=1, padx=(0, 14))
        self.symbol_combo.bind("<<ComboboxSelected>>", self._on_symbol_changed)
        ttk.Label(controls, text="合约").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.contract_combo = ttk.Combobox(controls, textvariable=self.contract_var, width=18, state="readonly")
        self.contract_combo.grid(row=0, column=3, padx=(0, 14))
        ttk.Button(controls, text="保存固定合约", command=self.save_override).grid(row=0, column=4, padx=4)
        ttk.Button(controls, text="恢复自动主力", command=self.set_automatic).grid(row=0, column=5, padx=4)
        ttk.Button(controls, text="刷新数据源", command=self.refresh_source).grid(row=0, column=6, padx=4)
        ttk.Button(controls, text="重新加载", command=self.refresh_contracts).grid(row=0, column=7, padx=4)

    def _build_context_tab(self) -> None:
        toolbar = ttk.Frame(self.context_tab)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="交易日").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.report_date_var, width=14).pack(side="left", padx=8)
        ttk.Button(toolbar, text="加载日报数据", command=self.load_report_context).pack(side="left")
        self.context_text = Text(self.context_tab, wrap="word", font=("Microsoft YaHei", 10))
        self.context_text.pack(fill="both", expand=True, pady=(10, 0))

    def _build_archive_tab(self) -> None:
        toolbar = ttk.Frame(self.archive_tab)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="刷新报告列表", command=self.load_reports).pack(side="left")
        ttk.Button(toolbar, text="读取选中报告", command=self.read_selected_report).pack(side="left", padx=8)
        body = ttk.Panedwindow(self.archive_tab, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(10, 0))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)
        self.report_tree = ttk.Treeview(
            left,
            columns=("date", "type", "title"),
            show="headings",
            height=18,
        )
        self.report_tree.heading("date", text="日期")
        self.report_tree.heading("type", text="类型")
        self.report_tree.heading("title", text="标题")
        self.report_tree.column("date", width=100, anchor="center")
        self.report_tree.column("type", width=120, anchor="center")
        self.report_tree.column("title", width=260)
        self.report_tree.pack(fill="both", expand=True)
        self.report_text = Text(right, wrap="word", font=("Microsoft YaHei", 10))
        self.report_text.pack(fill="both", expand=True)

    def _run_async(
        self,
        work: Callable[[], Any],
        done: Callable[[Any], None],
        *,
        busy: str = "处理中...",
    ) -> None:
        self.status_var.set(busy)

        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: self._show_error(exc))
            else:
                self.root.after(0, lambda: done(result))

        threading.Thread(target=runner, daemon=True).start()

    def _show_error(self, exc: Exception) -> None:
        self.status_var.set("操作失败")
        messagebox.showerror("AI Knowledge Base", str(exc))

    def refresh_contracts(self) -> None:
        self._run_async(self.service.contract_overview, self._apply_contracts, busy="正在加载合约...")

    def _apply_contracts(self, payload: dict[str, Any]) -> None:
        self.contract_rows = payload.get("products", [])
        for item in self.contract_tree.get_children():
            self.contract_tree.delete(item)
        symbols: list[str] = []
        for item in self.contract_rows:
            symbol = str(item["symbol"])
            symbols.append(symbol)
            self.contract_tree.insert(
                "",
                "end",
                values=(
                    symbol,
                    item.get("name", ""),
                    item.get("main_contract") or "-",
                    item.get("main_contract_date") or "-",
                    item.get("override_contract") or "自动主力",
                    len(item.get("available_contracts", [])),
                ),
            )
        self.symbol_combo["values"] = symbols
        if symbols and not self.symbol_var.get():
            self.symbol_var.set(symbols[0])
            self._on_symbol_changed()
        self.status_var.set(f"合约已加载：{len(self.contract_rows)} 个品种")

    def _on_contract_row_selected(self, _event: object) -> None:
        selection = self.contract_tree.selection()
        if not selection:
            return
        values = self.contract_tree.item(selection[0], "values")
        self.symbol_var.set(str(values[0]))
        self._on_symbol_changed()

    def _on_symbol_changed(self, _event: object | None = None) -> None:
        symbol = self.symbol_var.get()
        item = next((row for row in self.contract_rows if row["symbol"] == symbol), None)
        if not item:
            return
        contracts = [entry["contract"] for entry in item.get("available_contracts", [])]
        self.contract_combo["values"] = contracts
        self.contract_var.set(item.get("override_contract") or item.get("main_contract") or "")

    def save_override(self) -> None:
        symbol = self.symbol_var.get()
        contract = self.contract_var.get()
        if not symbol or not contract:
            messagebox.showwarning("AI Knowledge Base", "请选择品种和合约")
            return
        self._run_async(
            lambda: self.service.set_contract_override(symbol, contract),
            lambda result: self._after_contract_write(result, f"{symbol} 已固定为 {contract}"),
            busy="正在保存合约...",
        )

    def set_automatic(self) -> None:
        symbol = self.symbol_var.get()
        if not symbol:
            return
        self._run_async(
            lambda: self.service.set_contract_override(symbol, None),
            lambda result: self._after_contract_write(result, f"{symbol} 已恢复自动主力"),
            busy="正在恢复自动主力...",
        )

    def _after_contract_write(self, _result: dict[str, Any], message: str) -> None:
        self.status_var.set(message)
        self.refresh_contracts()

    def refresh_source(self) -> None:
        trade_date = date.today().isoformat()
        self._run_async(
            lambda: self.service.run_crawler("SH", trade_date),
            self._after_refresh,
            busy="正在刷新 FuturesIntelTool...",
        )

    def _after_refresh(self, result: dict[str, Any]) -> None:
        suffix = "（数据已新鲜）" if result.get("skipped") else ""
        self.status_var.set(f"刷新状态：{result.get('status', 'unknown')}{suffix}")
        if result.get("status") == "failed":
            messagebox.showerror("AI Knowledge Base", result.get("error") or "刷新失败")

    def load_report_context(self) -> None:
        trade_date = self.report_date_var.get().strip()
        self._run_async(
            lambda: self.service.report_context(trade_date, symbols=["SH", "V", "JM"]),
            lambda result: self._show_json(self.context_text, result),
            busy="正在加载日报数据...",
        )

    def load_reports(self) -> None:
        self._run_async(
            lambda: self.service.list_reports(limit=50),
            self._apply_reports,
            busy="正在加载往期报告...",
        )

    def _apply_reports(self, payload: dict[str, Any]) -> None:
        self.report_rows = payload.get("reports", [])
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        for item in self.report_rows:
            self.report_tree.insert(
                "",
                "end",
                iid=str(item["report_id"]),
                values=(
                    item.get("trade_date", ""),
                    item.get("report_type", ""),
                    item.get("title", ""),
                ),
            )
        self.status_var.set(f"报告已加载：{len(self.report_rows)} 条")

    def read_selected_report(self) -> None:
        selection = self.report_tree.selection()
        if not selection:
            messagebox.showwarning("AI Knowledge Base", "请先选择一份报告")
            return
        report_id = str(selection[0])
        self._run_async(
            lambda: self.service.read_report(report_id, max_tokens=4000),
            lambda result: self.report_text.replace("1.0", "end", result.get("content", "")),
            busy="正在读取报告...",
        )

    @staticmethod
    def _show_json(widget: Text, payload: dict[str, Any]) -> None:
        widget.replace("1.0", "end", json.dumps(payload, ensure_ascii=False, indent=2))


def default_settings() -> Settings:
    settings = Settings.from_env()
    if settings.backend != "native":
        return settings
    local_root = Path(os.getenv("LOCALAPPDATA", "")) / "FuturesIntelTool"
    config_path = local_root / "config" / "default.json"
    if not config_path.exists():
        return settings
    source_root = Path(r"E:\资讯爬虫")
    return replace(
        settings,
        backend="futures-intel",
        futures_intel_root=source_root if source_root.exists() else local_root,
        futures_intel_config=config_path,
        fetch_5m=True,
    )


def main() -> None:
    root = Tk()
    root.title("AI Knowledge")
    icon_path = Path(__file__).with_name("resources") / "ai-knowledge.ico"
    if icon_path.exists():
        root.iconbitmap(default=str(icon_path))
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
