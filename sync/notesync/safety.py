"""書き換えの前に元のファイルを残す(非機能要件「安全」: 削除しない、30日分残す)。"""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path


class Backup:
    def __init__(self, base: Path | None, keep_days: int = 30):
        self.base = base
        self.keep_days = keep_days
        self.stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    def save(self, vault: Path, path: Path) -> None:
        if self.base is None or not path.exists():
            return
        dest = self.base / self.stamp / vault.name / path.relative_to(vault)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)

    def prune(self) -> None:
        """keep_days より古い backup を消す(backup はプログラムのものなので消してよい)。"""
        if self.base is None or not self.base.exists():
            return
        limit = time.time() - timedelta(days=self.keep_days).total_seconds()
        for d in self.base.iterdir():
            if d.is_dir() and d.stat().st_mtime < limit:
                shutil.rmtree(d, ignore_errors=True)
