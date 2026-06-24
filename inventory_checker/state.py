"""前回チェック時の在庫状態を保存し、状態変化を検出する."""

from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    """URL ごとの最終在庫状態を JSON ファイルに永続化する."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open(encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, url: str) -> str | None:
        return self._data.get(url)

    def set(self, url: str, status: str) -> None:
        self._data[url] = status
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)
        tmp.replace(self.path)
