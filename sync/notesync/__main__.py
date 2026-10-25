"""使い方:

    python -m notesync once [--config 個人設定.yaml] [--dry-run]
    python -m notesync watch [--config 個人設定.yaml] [--interval 3]
    python -m notesync weekly [--config 個人設定.yaml]
    python -m notesync recover [--config 個人設定.yaml] [--run]

once は1回だけ同期する。watch は interval 分ごとに繰り返し、合間に Obsidian の「今すぐ共有へ」(Ctrl+Shift+S)を受けるとすぐ同期する(F-48)。weekly は今週の週報を今すぐ作り直す(F-29)。--hide / --only で今回だけ載せる節を変えられる。
recover は共有 vault に直接書かれたノートに id をつけ、たまった重い添付を移す(F-35)。--run がなければ試し運転。
--dry-run は書き込まず、やる予定だけを _仕組み/同期レポート.md に書く(F-23)。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .run import run_once


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="notesync", description="知見同期プログラム")
    ap.add_argument("command", choices=["once", "watch", "weekly", "recover"])
    ap.add_argument("--config", type=Path, default=config.default_config_path())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true", help="recover を試し運転でなく実行する")
    ap.add_argument("--interval", type=float, default=3.0, help="watch のときの間隔(分)")
    ap.add_argument("--hide", default="", help="weekly で今回だけ外す節(例: 同じノード,機密)")
    ap.add_argument("--only", default="", help="weekly で今回だけ載せる節をこれだけにする(例: 出荷準備度,担当者)")
    args = ap.parse_args(argv)
    try:
        cfg = config.load(args.config)
    except config.ConfigError as e:
        print(f"止めました: {e}", file=sys.stderr)
        return 2
    dry = True if args.dry_run else None
    if args.command == "recover":
        import time as _t

        from .recover import recover
        from .report import Report
        from .safety import Backup
        if not cfg.shared:
            print("止めました: 個人設定に shared を書いてください", file=sys.stderr)
            return 2
        r = Report(dry_run=not args.run)
        recover(cfg.member, cfg.code, cfg.personal, cfg.shared, cfg.shared_data, r,
                Backup(cfg.backup_dir), not args.run, _t.time())
        path = r.write(cfg.personal)
        print(f"{'拾い直しました' if args.run else '試し運転しました'}: 記録 {len(r.records)} 件。{path} を見てください")
        return 0
    if args.command == "weekly":
        from datetime import datetime

        from .ids import JST
        from .report import Report
        from .weekly import SECTIONS, make_weekly, sections_of
        if not cfg.shared or not cfg.report_dir:
            print("止めました: 個人設定に shared と report を書いてください", file=sys.stderr)
            return 2
        split = lambda t: [x.strip() for x in t.replace("、", ",").split(",") if x.strip()]
        hide, only = split(args.hide), split(args.only)
        unknown = [x for x in hide + only if x not in SECTIONS]
        if unknown:
            print(f"止めました: 知らない節 {'、'.join(unknown)}。使える節: {'、'.join(SECTIONS)}", file=sys.stderr)
            return 2
        r = Report(dry_run=bool(dry))
        made = make_weekly(cfg.shared, cfg.report_dir, datetime.now(JST).date(), r, bool(dry), force=True,
                           sections=sections_of(cfg.shared, hide, only))
        print(f"週報を作りました: {len(made)} 件({cfg.report_dir})")
        return 0
    while True:
        report = run_once(cfg, dry_run=dry)
        print(f"同期しました: 記録 {len(report.records)} 件、対応が必要 {len(report.todos)} 件、警告 {len(report.warnings)} 件")
        if args.command == "once":
            return 0
        # 3分待つ合間に「今すぐ共有へ」の合図を見る(F-48)
        from .now import wait
        wait(cfg, args.interval * 60, lambda c: run_once(c, dry_run=dry))


if __name__ == "__main__":
    sys.exit(main())
