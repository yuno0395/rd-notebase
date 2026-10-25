"""前回同期したときの内容(F-14)。

個人 vault の _仕組み/記録/同期の記録.json に置く(どの PC からも同じ記録を使うため。
v0.45 までの %APPDATA%\\知見同期\\state_<名前>.json は、新しい方がまだなければ読む)。消えても、個人 vault と共有 vault を
見比べて作り直せる(F-34): 中身が同じなら同期済み、違えば競合として扱い、上書きしない。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:32]


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


class State:
    def __init__(self, path: Path | None, old: Path | None = None):
        self.path = path
        self.items: dict[str, dict] = {}
        self.broken = False
        src = path if path and path.exists() else old if old and old.exists() else None
        if src:
            try:
                data = json.loads(src.read_text(encoding="utf-8"))
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
