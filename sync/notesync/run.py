"""1回分の同期を行う。"""

from __future__ import annotations

import time

from .autofill import run_autofill
from .boxcopies import report_box_copies
from .heavy import keep_rules, move_heavy
from .history import record_history
from .weekly import maybe_weekly
from .assign import Vault, assign_ids, collect_used, fix_links, name_index, report_same_names
from . import ids
from .config import Config
from .report import Report
from .safety import Backup
from .share import Context, run_share
from .state import State


def split_name(stem: str) -> str:
    return ids.split_filename(stem)[1]


def vaults_of(cfg: Config) -> list[Vault]:
    vs = [Vault("個人", cfg.personal, assign=True)]
    if cfg.shared:
        vs.append(Vault("共有", cfg.shared, assign=False))
    vs += [Vault("機密", p, assign=True) for p in cfg.secret if p.exists()]
    return vs


def run_once(cfg: Config, dry_run: bool | None = None, now: float | None = None) -> Report:
    dry = cfg.dry_run if dry_run is None else dry_run
    now = time.time() if now is None else now
    report = Report(dry_run=dry)
    backup = Backup(cfg.backup_dir)
    vaults = vaults_of(cfg)
    for p in cfg.secret:
        if not p.exists():
            report.warn(f"機密フォルダが見つかりません: {p}(権限か設定を確かめてください)")

    used = collect_used(vaults)
    renamed: dict[str, dict[str, str]] = {}
    for v in vaults:
        if v.assign:
            renamed[v.label + str(v.root)] = assign_ids(
                v, cfg.member, cfg.code, used, report, backup, dry, now, cfg.idle_seconds)

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
    fix_links(vaults[0], *planned(open_vaults), report, backup, dry)
    for v in vaults:
        if v.label == "機密":
            fix_links(v, *planned([v]), report, backup, dry)

    report_same_names(vaults, report)
    # 重い添付を 開発データ/ へ移し、リンクを書き換える(F-17〜20)。個人 vault だけ
    move_heavy(cfg.personal, cfg.shared, cfg.shared_data, cfg.member, report, backup, dry, now, cfg.idle_seconds)
    report_box_copies([(v.label, v.root) for v in vaults], report)  # F-16

    # おまけの自動入力(F-26・F-27・F-31)。集める前に書いて、同じ同期で共有に届ける
    run_autofill(cfg.personal, cfg.shared, report, backup, dry, now, cfg.idle_seconds)

    # 集約と再配布(F-05〜11、F-14、F-15)
    if cfg.shared and cfg.shared.exists():
        state = State(cfg.state_path)
        if state.broken:
            report.warn("前回同期の記録が壊れていたので、見比べて作り直しました(F-34)")
        ctx = Context(member=cfg.member, personal=cfg.personal, shared=cfg.shared,
                      secret=[p for p in cfg.secret if p.exists()], report=report, backup=backup,
                      state=state, dry_run=dry, now=now, idle_seconds=cfg.idle_seconds,
                      data_root=cfg.shared_data, keep=keep_rules(cfg.shared))
        run_share(ctx)
        record_history(cfg.personal, cfg.shared, cfg.member, report, dry, now)  # F-31・F-32
        maybe_weekly(cfg.member, cfg.shared, cfg.report_dir, now, report, dry)  # F-29
        if not dry:
            state.save()
    elif cfg.shared:
        report.warn(f"共有 vault が見つかりません: {cfg.shared}(Box Drive が止まっていないか確かめてください)")

    report.write(cfg.personal)
    if not dry:
        backup.prune()
    return report
