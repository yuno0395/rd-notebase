"""F-48: 「今すぐ共有へ」(Obsidian の Ctrl+Shift+S)の合図を受けて、すぐ1回同期する。

Obsidian のスクリプトが、この PC の %APPDATA%\\知見同期\\今すぐ\\<時刻>.json に合図を置く。
共有クラウドフォルダの外なので、同じ人の別の PC に合図が届いて二重に動くことはない。
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


def take_signals(folder: Path, personal: Path, now: float | None = None,
                 decks: dict[Path, dict] | None = None) -> list[Path]:
    """自分の個人 vault あての合図を拾って消す。返すのは結果を書く場所。

    合図に "資料"(説明資料の依頼。F-59)か "つなぐ"(説明資料をつなぐ依頼。F-59b)があれば、
    decks に 結果を書く場所 → 依頼 を入れる(つなぐは {"つなぐ": {...}} の形で)。"""
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
        done = p.with_name(p.stem + DONE)
        if decks is not None and isinstance(data.get("資料"), dict):
            decks[done] = data["資料"]
        elif decks is not None and isinstance(data.get("つなぐ"), dict):
            decks[done] = {"つなぐ": data["つなぐ"]}
        out.append(done)
    return out


def write_result(path: Path, ok: bool, message: str, report=None, open_: str | None = None) -> None:
    """open_ は Obsidian で開くファイル(個人 vault の中のパス)。"""
    data = {"ok": ok, "message": message}
    if open_ is not None:
        data["open"] = open_
    if report is not None:
        data.update(records=len(report.records), todos=len(report.todos), warnings=len(report.warnings))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def run_now(cfg: Config, results: list[Path], run_once, decks: dict[Path, dict] | None = None) -> None:
    """押した=書き終わった合図なので、保存して間もないノートも待たずに送る。
    説明資料の依頼(F-59)は、同期のあと共有 vault のノートで作る。"""
    decks = decks or {}
    now_cfg = replace(cfg, idle_seconds=0)
    try:
        report = run_once(now_cfg)
    except Exception as e:  # 止まっても watch は続ける
        for r in results:
            write_result(r, False, f"同期で止まりました({type(e).__name__}: {e})")
        return
    finally:
        # vault の場所を直したら(F-50)、watch の設定にも移す
        cfg.personal, cfg.shared, cfg.secret = now_cfg.personal, now_cfg.shared, now_cfg.secret
    if getattr(report, "stopped", ""):
        for r in results:
            write_result(r, False, report.stopped, report)
        print(f"今すぐ共有へ: {report.stopped}")
        return
    if getattr(report, "skipped", ""):  # 同じ個人 vault を別の PC が同期している(F-49)
        msg = f"{report.skipped} の PC が同期しているところなので、送れませんでした。少し待ってからもう一度押してください"
        for r in results:
            write_result(r, False, msg, report)
        print(f"今すぐ共有へ: {msg}")
        return
    if report.dry_run:
        msg = "試し運転なので共有へは送っていません。同期レポートを見てください"
    elif report.todos or report.warnings:
        msg = f"共有へ送りました。対応が必要 {len(report.todos)} 件・警告 {len(report.warnings)} 件。同期レポートを見てください"
    else:
        msg = "共有へ送りました"
    for r in results:
        if r in decks and "つなぐ" in decks[r]:
            join_deck(cfg, r, decks[r]["つなぐ"], report)
        elif r in decks:
            make_deck(cfg, r, decks[r], report)
        else:
            write_result(r, True, msg, report)
    print(f"今すぐ共有へ: {msg}")


def make_deck(cfg: Config, result: Path, req: dict, report) -> None:
    """説明資料の図を作り、結果に開くファイルを書く(要件書 F-59・F-59b)。作れなくても同期の結果はそのまま。"""
    from datetime import datetime

    from . import deck
    from .ids import JST
    if not cfg.shared:
        write_result(result, False, "個人設定に shared がないので、説明資料を作れません", report)
        return
    try:
        path, d = deck.make(cfg.shared, cfg.personal, str(req.get("note", "")), str(req.get("筋書き", "")),
                            str(req.get("ひとこと", "")), cfg.member, datetime.now(JST).date())
    except deck.DeckError as e:
        write_result(result, False, str(e), report)
        return
    except Exception as e:  # 止まっても watch は続ける
        write_result(result, False, f"説明資料を作れませんでした({type(e).__name__}: {e})", report)
        return
    msg = f"説明資料を作りました({d.count}枚。足りないところ {len(d.gaps)})"
    if any(g[0] == "(ひな形)" for g in d.gaps):
        msg += "。ひな形を読めませんでした"
    if d.story == deck.OUTSIDE:
        msg += "。社外に出す前に中身を確かめてください"
    write_result(result, True, msg, report, open_=path.relative_to(cfg.personal).as_posix())
    print(f"説明資料: {path}")


def join_deck(cfg: Config, result: Path, req: dict, report) -> None:
    """選んだ説明資料をつなぐ(要件書 F-59b)。"""
    from datetime import datetime

    from .deck_draw import TemplateError, join_decks
    from .ids import JST
    paths = [cfg.personal / str(p) for p in req.get("資料") or []]
    if len(paths) < 1 or not all(p.is_file() for p in paths):
        write_result(result, False, "つなぐ資料が見つかりません", report)
        return
    try:
        path = join_decks(paths, cfg.personal, str(req.get("機密区分") or ""), req.get("向け") != "社外",
                          datetime.now(JST).date())
    except TemplateError as e:
        write_result(result, False, str(e), report)
        return
    except Exception as e:  # 止まっても watch は続ける
        write_result(result, False, f"説明資料をつなげませんでした({type(e).__name__}: {e})", report)
        return
    write_result(result, True, f"説明資料をつなぎました({len(paths)} つ)", report,
                 open_=path.relative_to(cfg.personal).as_posix())
    print(f"説明資料をつなぎました: {path}")


RETRY_SECONDS = 30  # 書いている途中で見送ったものを、やり直すまでの最短の間


def next_wait(interval: float, report, idle_seconds: int) -> float:
    """次の同期までの秒数。書いている途中で見送ったものがあれば、3分待たずに少ししてからやり直す
    (保存してから idle_seconds たてば送れるので)。"""
    if getattr(report, "deferred", False):
        return min(interval, max(RETRY_SECONDS, idle_seconds + 5))
    return interval


def wait(cfg: Config, seconds: float, run_once, folder: Path | None = None, step: float = 0.5) -> None:
    """次の定期の同期まで待つ。合間に合図を見て、あればすぐ同期する。"""
    folder = folder or signal_dir()
    end = time.monotonic() + seconds
    while True:
        decks: dict[Path, dict] = {}
        results = take_signals(folder, cfg.personal, decks=decks)
        if results:
            run_now(cfg, results, run_once, decks)
        left = end - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(step, left))
