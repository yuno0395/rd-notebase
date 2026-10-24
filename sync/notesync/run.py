"""1回分の同期を行う。"""

from __future__ import annotations

import time

from .assign import Vault, assign_ids, collect_used, fix_links, name_index, report_same_names
from . import ids
from .config import Config
from .report import Report
from .safety import Backup


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
    report.write(cfg.personal)
    if not dry:
        backup.prune()
    return report
