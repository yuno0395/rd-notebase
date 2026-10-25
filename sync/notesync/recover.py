"""F-35: 止まっていた間に共有 vault へ直接書かれたものを拾い直す。

- 共有 vault の id のないノートに id をつけ、名前だけのリンクを id つきに直す(F-01〜04 を共有にも)
- 共有 vault の `_仕組み/attachments/<id>/` にたまった重い添付を 開発データ/ へ移し、
  共有のリンクを `開発データ/...` の形にする

いつもの同期では、見つけたものを同期レポートに出すだけにする。人が確かめてから、
`python -m notesync recover`(試し運転)→ `python -m notesync recover --run`(反映)で行う。
手で共有されたノート(前回の記録がないもの)は、いつもの同期が見比べて扱う(F-34)。
"""

from __future__ import annotations

from pathlib import Path

from .assign import Vault, assign_ids, collect_used, fix_links, name_index
from .heavy import ATTACH, DATA_PREFIX, Mover, free_name, is_heavy, keep_rules, relink, shared_folder_of
from .report import Report
from .safety import Backup
from .state import digest
from .vault import box_copy_of, is_hidden, iter_md, needs_id, notes, read, write


def pending(shared: Path, data_root: Path | None) -> tuple[list[str], list[str]]:
    """(id のないノート, 重い添付) の相対パス。"""
    no_id = [n.rel for n in notes(shared) if needs_id(n)] if shared.exists() else []
    heavy = []
    base = shared / ATTACH
    if data_root and base.exists():
        rules = keep_rules(shared)
        for f in sorted(base.rglob("*")):
            if f.is_file() and not any(is_hidden(x) for x in f.relative_to(base).parts) \
                    and not box_copy_of(f)[0] and is_heavy(f, rules):
                heavy.append(f.relative_to(shared).as_posix())
    return no_id, heavy


def report_pending(shared: Path | None, data_root: Path | None, report: Report) -> None:
    if not shared or not shared.exists():
        return
    try:
        no_id, heavy = pending(shared, data_root)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"共有 vault の拾い直しの確認で止まりました({type(e).__name__}: {e})")
        return
    if no_id:
        ex = "、".join(no_id[:3]) + (" ほか" if len(no_id) > 3 else "")
        report.todo(f"拾い直し: 共有 vault に id のないノートが {len(no_id)} 件あります({ex})。"
                    "`python -m notesync recover` で試し運転し、よければ `--run` をつけて反映してください")
    if heavy:
        report.todo(f"拾い直し: 共有 vault の _仕組み/attachments/ に重い添付が {len(heavy)} 件あります。"
                    "`python -m notesync recover` で試し運転し、よければ `--run` をつけて 開発データ/ へ移してください")


def recover(member: str, code: str, personal: Path, shared: Path, data_root: Path | None,
            report: Report, backup: Backup, dry_run: bool, now: float) -> None:
    sv = Vault("共有", shared, assign=True)
    pv = Vault("個人", personal, assign=False)
    used = collect_used([pv, sv])
    renamed = assign_ids(sv, member, code, used, report, backup, dry_run, now, 0)
    index, stems = name_index([pv, sv])
    if dry_run:
        for old, new in renamed.items():
            stems.discard(old.lower())
            index[new.split("_", 1)[1].lower()].add(new)
    fix_links(sv, index, stems, report, backup, dry_run)
    if data_root:
        move_shared_heavy(shared, data_root, member, report, backup, dry_run, now)


def move_shared_heavy(shared: Path, data_root: Path, member: str, report: Report, backup: Backup,
                      dry_run: bool, now: float) -> None:
    m = Mover(shared, shared, data_root, member, report, backup, dry_run, now, 0)
    base = shared / ATTACH
    if not base.exists():
        return
    shared_notes = [(p, rel.as_posix()) for p, rel in iter_md(shared)]
    for note_dir in sorted(d for d in base.iterdir() if d.is_dir()):
        note_id = note_dir.name
        top = shared_folder_of(shared, note_id) or "共通"
        for f in sorted(note_dir.rglob("*")):
            if not f.is_file() or box_copy_of(f)[0] or not is_heavy(f, m.rules):
                continue
            rel_name = f.relative_to(note_dir).as_posix()
            target = data_root / top / note_id / rel_name
            same = target.exists() and digest(target) == digest(f)
            final = target if same else free_name(target)
            url = DATA_PREFIX + final.relative_to(data_root).as_posix()
            url = f"<{url}>" if " " in url else url
            for p, rel in shared_notes:
                own = p.stem.upper().startswith(note_id.upper() + "_")
                text = read(p)
                new = relink(text, note_id, rel_name, url, own)
                if new != text:
                    report.record(f"共有: リンクを書き換えた {rel}({rel_name})")
                    if not dry_run:
                        backup.save(shared, p)
                        write(p, new)
            m.move_file(f, target)
            report.record(f"共有: 重い添付を移した {ATTACH}/{note_id}/{rel_name} → "
                          f"開発データ/{final.relative_to(data_root).as_posix()}")
