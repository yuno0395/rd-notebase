"""使い方:

    python -m notesync once [--config 個人設定.yaml] [--dry-run]
    python -m notesync watch [--config 個人設定.yaml] [--interval 3]

once は1回だけ同期する。watch は interval 分ごとに繰り返す。
--dry-run は書き込まず、やる予定だけを _仕組み/同期レポート.md に書く(F-23)。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config
from .run import run_once


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="notesync", description="知見同期プログラム")
    ap.add_argument("command", choices=["once", "watch"])
    ap.add_argument("--config", type=Path, default=config.default_config_path())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--interval", type=float, default=3.0, help="watch のときの間隔(分)")
    args = ap.parse_args(argv)
    try:
        cfg = config.load(args.config)
    except config.ConfigError as e:
        print(f"止めました: {e}", file=sys.stderr)
        return 2
    dry = True if args.dry_run else None
    while True:
        report = run_once(cfg, dry_run=dry)
        print(f"同期しました: 記録 {len(report.records)} 件、対応が必要 {len(report.todos)} 件、警告 {len(report.warnings)} 件")
        if args.command == "once":
            return 0
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    sys.exit(main())
