"""前回同期したときの内容(F-14)。

%APPDATA%\\知見同期\\state_<名前>.json に置く。消えても、個人 vault と共有 vault を
見比べて作り直せる(F-34): 中身が同じなら同期済み、違えば競合として扱い、上書きしない。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:32]


class State:
    def __init__(self, path: Path | None):
        self.path = path
        self.items: dict[str, dict] = {}
        self.broken = False
        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.items = dict(data.get("items") or {})
            except (OSError, ValueError, AttributeError):
                self.broken = True  # 作り直す(F-34)

    def get(self, key: str) -> dict | None:
        return self.items.get(key)

    def set(self, key: str, value: dict) -> None:
        self.items[key] = value

    def starting(self, prefix: str) -> dict[str, dict]:
        return {k: v for k, v in self.items.items() if k.startswith(prefix)}

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "items": self.items}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.path)
