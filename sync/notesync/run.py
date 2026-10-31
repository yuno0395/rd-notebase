"""1回分の同期を行う。"""

from __future__ import annotations

import time

from .attachfix import fix_attachments
from .fresh import fresh_ids
from .autofill import run_autofill
from .copies import report_sync_copies, tidy_layout_copies
from .heavy import keep_rules, move_heavy
from .history import record_history
from .schedule import update_schedules
from .weekly import maybe_weekly
from .daily import update_daily
from .recover import report_pending
from .assign import Vault, assign_ids, collect_used, fix_links, name_index, report_same_names
from . import ids
from .config import Config
from .relocate import follow
from .guard import check_places
from .outward import check_outward
from .lock import Busy, Lock
from .report import Report
from .safety import Backup
from .share import Context, run_share
from .vault import OLD_DIST, notes
from .state import State


def split_name(stem: str) -> str:
    return ids.split_filename(stem)[1]


def vaults_of(cfg: Config) -> list[Vault]:
    vs = [Vault("個人", cfg.personal, assign=True)]
    if cfg.shared:
        vs.append(Vault("共有", cfg.shared, assign=False))
    vs += [Vault("機密", p, assign=True) for p in cfg.secret if p.exists()]
    return vs


def _vkey(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return ()


def notice_new_version(personal, shared, report: Report) -> None:
    """管理者が新しい版を出したら、同期レポートで知らせる(当てるのは各自の準備の bat。仕様書「bat 1つで準備と更新」)。"""
    if not shared:
        return
    try:
        latest = (shared / "_仕組み/tools/準備/最新の版.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return
    try:
        mine = (personal / "_仕組み/記録/版.txt").read_text(encoding="utf-8").strip()
    except OSError:
        mine = ""
    if _vkey(latest) and (not _vkey(mine) or _vkey(mine) < _vkey(latest)):
        report.todo(f"新しい版 {latest} があります(いまは {mine or '版なし'})。共有 vault の _仕組み/tools/準備/ の "
                    "bat(PL はプロジェクトリーダー.bat、ほかはチームメンバー.bat)を押してください")


def run_once(cfg: Config, dry_run: bool | None = None, now: float | None = None) -> Report:
    """1回分の同期。同じ個人 vault を別の PC が同期している間は見送る(複数の PC で使う)。"""
    dry = cfg.dry_run if dry_run is None else dry_run
    now = time.time() if now is None else now
    # F-50: vault の名前や場所が変わっていたら、新しい場所を見つけて設定を直す
    moved, move_warnings = follow(cfg, dry=dry)
    moved, move_warnings = cfg.moved + moved, cfg.move_warnings + move_warnings
    cfg.moved, cfg.move_warnings = [], []
    if not cfg.personal.exists():
        # 古い名前のフォルダを作り直さない(作ると、そこへ共有のノートが配られてしまう)
        report = Report(dry_run=dry)
        report.stopped = (f"個人 vault が見つかりません: {cfg.personal}。名前を変えたなら、設定ファイル "
                          f"{cfg.config_path or ''} の personal を新しい場所に直してください")
        for w in move_warnings:
            report.warn(w)
        return report
    missing = [p for p in cfg.secret if not p.exists()]
    if missing:
        # 機密の言葉が混ざっていないかを確かめられないので、共有へは送らない
        report = Report(dry_run=dry)
        report.stopped = (f"機密フォルダが見つかりません: {'、'.join(str(p) for p in missing)}。機密の言葉の確かめが"
                          f"できないので、同期を止めました。名前を変えたなら設定ファイル {cfg.config_path or ''} の"
                          " secret を直し、権限が外れたなら管理者に聞いてください")
        report.warn(report.stopped)
        for w in move_warnings:
            report.warn(w)
        for r in moved:
            report.record(r)
        report.write(cfg.personal)
        return report
    problems = check_places(cfg)
    if problems:
        # 書き間違えた場所のファイルを改名したり、そこへノートを集めたりしないように、何も書かずに止める(F-55)
        report = Report(dry_run=dry)
        report.stopped = "設定の場所がおかしいので、同期を止めました: " + " / ".join(problems)
        report.todo(f"設定の場所がおかしいので、同期を止めました。設定ファイル {cfg.config_path or 'config.yaml'} を"
                    "直してください(下の警告)")
        for w in problems + move_warnings:
            report.warn(w)
        if "個人" not in " ".join(problems):
            report.write(cfg.personal)
        return report
    lock = Lock(cfg.lock_path)
    try:
        lock.acquire()
    except Busy as b:
        report = Report(dry_run=dry)
        report.skipped = b.pc
        return report
    try:
        report = _run(cfg, dry, now, moved, move_warnings)
        return report
    finally:
        lock.release()


def _run(cfg: Config, dry: bool, now: float, moved: list[str] = (), move_warnings: list[str] = ()) -> Report:
    report = Report(dry_run=dry)
    for r in moved:
        report.record(r)
    for w in move_warnings:
        report.warn(w)
    backup = Backup(cfg.backup_dir)
    if (cfg.personal / OLD_DIST).is_dir():
        # v0.67 で 90_共有/ をなくした。移し替えの前に同期すると、配られたノートが2つずつになる
        report.warn(f"個人 vault に {OLD_DIST}/ が残っているので、同期を止めています。準備の bat で仕組みを更新してください"
                    "(版 0.2.1 の移し替え tools/migrate_v067.py が、他の人のノートを共有と同じ場所へ移します)")
        report.write(cfg.personal)
        return report
    vaults = vaults_of(cfg)

    # F-28: 作ったばかりでテンプレートのままのノートには触らない(取り消しを邪魔しないため)
    try:
        fresh = fresh_ids(cfg.personal, cfg.shared, now)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        fresh = set()
        report.warn(f"作成履歴の読み取りで止まりました({type(e).__name__}: {e})")
    used = collect_used(vaults)
    shared_stems = {n.stem for n in notes(cfg.shared) if n.file_id} if cfg.shared and cfg.shared.exists() else set()
    renamed: dict[str, dict[str, str]] = {}
    for v in vaults:
        if v.assign:
            personal = v.label == "個人"
            renamed[v.label + str(v.root)] = assign_ids(
                v, cfg.me, cfg.code, used, report, backup, dry, now, cfg.idle_seconds,
                fresh if personal else frozenset(), shared_stems if personal else frozenset())

    # リンクを直すのは、個人と機密の中だけ。機密のノートは機密の中のノートにだけつなぐ(F-40)
    def planned(vs):
        index, stems = name_index(vs)
        if dry:
            # 試し運転では名前を変えていないので、つけるはずの名前を表に足しておく
            for v in vs:
                for old, new in renamed.get(v.label + str(v.root), {}).items():
                    stems.discard(old.lower())
                    index[split_name(new).lower()].add(new)
        return index, stems

    open_vaults = [v for v in vaults if v.label != "機密"]
    fix_links(vaults[0], *planned(open_vaults), report, backup, dry, cfg.me)
    for v in vaults:
        if v.label == "機密":
            fix_links(v, *planned([v]), report, backup, dry)

    # id を振ったノートの添付を _仕組み/attachments/<id>/ へ移し、リンクの形をそろえる(F-17b)
    fix_attachments(cfg.personal, renamed.get(vaults[0].label + str(vaults[0].root), {}),
                    report, backup, dry, now, cfg.idle_seconds, cfg.me)
    report_same_names(vaults, report)
    # 重い添付を 開発データ/ へ移し、リンクを書き換える(F-17〜20)。個人 vault だけ
    move_heavy(cfg.personal, cfg.shared, cfg.shared_data, cfg.member, report, backup, dry, now, cfg.idle_seconds,
               me=cfg.me)
    report_sync_copies([(v.label, v.root) for v in vaults], report)  # F-16
    tidy_layout_copies(cfg.personal, report, backup, dry)  # 2台で使うとできる画面配置の複製

    # おまけの自動入力(F-26・F-27・F-31)。集める前に書いて、同じ同期で共有に届ける
    started = run_autofill(cfg.personal, cfg.shared, report, backup, dry, now, cfg.idle_seconds, fresh,
                           cfg.me)

    # 集約と再配布(F-05〜11、F-14、F-15)
    if cfg.shared and cfg.shared.exists():
        state = State(cfg.state_path)
        if state.broken:
            report.warn("前回同期の記録が壊れていたので、見比べて作り直しました(F-34)")
        ctx = Context(member=cfg.member, me=cfg.me, personal=cfg.personal, shared=cfg.shared,
                      secret=[p for p in cfg.secret if p.exists()], report=report, backup=backup,
                      state=state, dry_run=dry, now=now, idle_seconds=cfg.idle_seconds,
                      data_root=cfg.shared_data, keep=keep_rules(cfg.shared), fresh=fresh)
        run_share(ctx)
        record_history(cfg.personal, cfg.shared, cfg.member, report, dry, now, started, me=cfg.me)  # F-31・F-32・F-54
        update_schedules(cfg.personal, cfg.shared, cfg.me, report, backup, dry, now, cfg.idle_seconds)  # F-53
        maybe_weekly(cfg.shared, cfg.report_dir, now, report, dry)  # F-29(誰の PC でも作る)
        report_pending(cfg.shared, cfg.shared_data, report)  # F-35
        if not dry:
            state.save()
    elif cfg.shared:
        report.warn(f"共有 vault が見つかりません: {cfg.shared}(同期アプリ(Box Drive・OneDrive など)が止まっていないか確かめてください)")

    try:
        check_outward(cfg, report)  # F-56: 外へ送る機能がオンになっていないか
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"外へ送る機能の確かめで止まりました({type(e).__name__}: {e})")
    update_daily(cfg.personal, cfg.shared, cfg.member, report, backup, dry, now, cfg.idle_seconds)  # F-33
    notice_new_version(cfg.personal, cfg.shared, report)
    report.write(cfg.personal)
    if not dry:
        backup.prune()
    return report
