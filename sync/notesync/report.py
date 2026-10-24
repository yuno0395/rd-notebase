"""F-21: _仕組み/同期レポート.md(要件書「同期レポート」)。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from .ids import JST

REPORT_NAME = "_仕組み/同期レポート.md"
KEEP_DAYS = 30
RECORD_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) ")


class Report:
    def __init__(self, dry_run: bool = False, now: datetime | None = None):
        self.dry_run = dry_run
        self.now = now or datetime.now(JST)  # PC の時計の設定によらず日本時間で書く
        self.todos: list[str] = []
        self.checked: set[str] = set()  # チェックがついたまま残す行(試し運転で答えを消さないため)
        self.warnings: list[str] = []
        self.records: list[str] = []

    def todo(self, text: str, checked: bool = False) -> None:
        if text not in self.todos:
            self.todos.append(text)
        if checked:
            self.checked.add(text)

    def warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def record(self, text: str) -> None:
        self.records.append(text)

    def render(self, old_text: str = "") -> str:
        stamp = self.now.strftime("%Y-%m-%d %H:%M")
        prefix = "予定: " if self.dry_run else ""
        new_records = [f"- {stamp} {prefix}{r}" for r in self.records]
        limit = (self.now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
        old_records = []
        in_records = False
        for line in old_text.splitlines():
            if line.startswith("## "):
                in_records = line.startswith("## 記録")
                continue
            m = RECORD_LINE.match(line)
            if in_records and m and m.group(1) >= limit:
                old_records.append(line)
        title = f"# 同期レポート(最終更新 {stamp}" + (" 試し運転" if self.dry_run else "") + ")"
        out = [title, "", "## 対応が必要"]
        out += [f"- [{'x' if t in self.checked else ' '}] {t}" for t in self.todos] or ["(なし)"]
        out += ["", "## 警告"]
        out += [f"- {w}" for w in self.warnings] or ["(なし)"]
        out += ["", f"## 記録(新しい順、直近 {KEEP_DAYS} 日)"]
        out += list(reversed(new_records)) + old_records
        return "\n".join(out) + "\n"

    def write(self, personal: Path) -> Path:
        path = personal / REPORT_NAME
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(old), encoding="utf-8", newline="\n")
        return path
