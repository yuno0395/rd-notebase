"""F-48: 「今すぐ共有へ」(Obsidian の Ctrl+Shift+S)の合図を受けて、すぐ1回同期する。

Obsidian のスクリプトが、この PC の %APPDATA%\\知見同期\\今すぐ\\<時刻>.json に合図を置く。
Box の外なので、同じ人の別の PC に合図が届いて二重に動くことはない。
合図には個人 vault の場所が書いてあり、自分の個人 vault の合図だけを拾う
(1台の PC で2人分を試すときも取り違えない)。
終わったら <時刻>.done.json に結果を書き、Obsidian がそれを読んで右上に出す。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from pathlib import Path

from . import config
from .config import Config

SIGNAL_DIR = "今すぐ"
DONE = ".done.json"
KEEP_SECONDS = 600  # 読まれなかった結果と古い合図は10分で消す


def signal_dir() -> Path:
    return config.default_config_path().parent / SIGNAL_DIR


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def take_signals(folder: Path, personal: Path, now: float | None = None) -> list[Path]:
    """自分の個人 vault あての合図を拾って消す。返すのは結果を書く場所。"""
    now = time.time() if now is None else now
    out = []
    if not folder.is_dir():
        return out
    for p in sorted(folder.glob("*.json")):
        if p.name.endswith(DONE):
            if now - p.stat().st_mtime > KEEP_SECONDS:
                p.unlink(missing_ok=True)
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            vault = Path(str(data.get("vault", "")))
        except (OSError, ValueError, AttributeError):
            if now - p.stat().st_mtime > KEEP_SECONDS:
                p.unlink(missing_ok=True)
            continue
        if not str(vault) or not _same(vault, personal):
            if now - p.stat().st_mtime > KEEP_SECONDS:
                p.unlink(missing_ok=True)  # 動いていない人あての合図
            continue
        p.unlink(missing_ok=True)
        out.append(p.with_name(p.stem + DONE))
    return out


def write_result(path: Path, ok: bool, message: str, report=None) -> None:
    data = {"ok": ok, "message": message}
    if report is not None:
        data.update(records=len(report.records), todos=len(report.todos), warnings=len(report.warnings))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def run_now(cfg: Config, results: list[Path], run_once) -> None:
    """押した=書き終わった合図なので、保存して間もないノートも待たずに送る。"""
    try:
        report = run_once(replace(cfg, idle_seconds=0))
    except Exception as e:  # 止まっても watch は続ける
        for r in results:
            write_result(r, False, f"同期で止まりました({type(e).__name__}: {e})")
        return
    if report.dry_run:
        msg = "試し運転なので共有へは送っていません。同期レポートを見てください"
    elif report.todos or report.warnings:
        msg = f"共有へ送りました。対応が必要 {len(report.todos)} 件・警告 {len(report.warnings)} 件。同期レポートを見てください"
    else:
        msg = "共有へ送りました"
    for r in results:
        write_result(r, True, msg, report)
    print(f"今すぐ共有へ: {msg}")


def wait(cfg: Config, seconds: float, run_once, folder: Path | None = None, step: float = 2.0) -> None:
    """次の定期の同期まで待つ。合間に合図を見て、あればすぐ同期する。"""
    folder = folder or signal_dir()
    end = time.monotonic() + seconds
    while True:
        results = take_signals(folder, cfg.personal)
        if results:
            run_now(cfg, results, run_once)
        left = end - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(step, left))
