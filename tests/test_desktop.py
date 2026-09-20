from __future__ import annotations

import os
from pathlib import Path

from futures_kb.desktop import default_settings, main


def test_desktop_entry_point_is_importable() -> None:
    assert callable(main)


def test_desktop_defaults_to_futures_intel_when_user_config_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    local_root = tmp_path / "FuturesIntelTool"
    config_dir = local_root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "default.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("FUTURES_KB_BACKEND", raising=False)
    monkeypatch.delenv("FUTURES_INTEL_CONFIG", raising=False)
    monkeypatch.delenv("FUTURES_INTEL_ROOT", raising=False)

    settings = default_settings()

    assert settings.backend == "futures-intel"
    assert settings.futures_intel_config == config_dir / "default.json"
