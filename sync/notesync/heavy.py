"""F-17〜20: 重い添付を vault の外の 開発データ/ へ移し、リンクを書き換える(仕様書「重い添付ファイルの置き場所」)。

- vault に残すもの: 画像・PDF・ノート(.md)・20MB 未満の動画。それ以外は重い添付。
- 置き場所: ノートを共有していれば 開発データ/<共有でのフォルダ>/<id>/(プロジェクト名か 共通)、
  まだなら 開発データ/_個人/<名前>/<id>/。共有されたら _個人/ からプロジェクトへ移す(F-20)。
- 個人 vault のリンクは、その PC の `file:///` に書き換える(F-18)。共有 vault では
  `開発データ/...` の相対パスにし、配るときにその人の `file:///` に直す(F-19、share.py の Context.copy)。
- 共有しないノート(visibility: 個人・type: メモ・00_日誌/ のノートと日誌の添付)の重い添付は、
  チーム全員が見られる 開発データ/ ではなく、個人設定の private_data(自分だけが見られるフォルダ)の
  <id>/ へ移す(F-17c、仕様書 v0.83)。private_data がなければ移さず vault に残して知らせる。
  共有するノートに変わったら private_data から 開発データ/ へ、共有しないノートに変わったら
  開発データ/_個人/ から private_data へ移す。
- 機密フォルダの添付は動かさない(F-40)。消すことはしない。移す前と後はレポートに残す。
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

from . import frontmatter, ids
from . import visibility as vis
from .report import Report
from .safety import Backup
from .state import digest
from .vault import SYSTEM_DIR, sync_copy_of, is_hidden, iter_md, read, theirs_file, write

ATTACH = f"{SYSTEM_DIR}/attachments"
DATA_PREFIX = "開発データ/"
PERSONAL_DIR = "_個人"
DIARY_DIR = "日誌"  # _仕組み/attachments/日誌/<日付やメモの名前>/(id のない日誌・メモの添付)
DIARY_TOP = "00_PIP"       # 自分だけのフォルダ(デイリー・メモ。)
OLD_DIARY_TOP = "00_日誌"  # v0.89 までの名前
# 前回の private_data を覚えておくファイル(PC ごと。config.yaml と同じ場所)
PRIVATE_MARK = "自分用の添付の場所_前回.txt"

DEFAULT_KEEP = {
    "images": ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"],
    "pdf": True,
    "video": ["mp4", "webm", "mov"],
    "video_max_mb": 20,
}

WIKI = re.compile(r"!?\[\[([^\[\]|#\n]+)(#[^\[\]|\n]*)?(\|[^\[\]\n]*)?\]\]")
MDLINK = re.compile(r"!?\[([^\[\]\n]*)\]\((<[^>\n]+>|[^)\s]+)\)")


def keep_rules(shared: Path | None) -> dict:
    rules = dict(DEFAULT_KEEP)
    if shared:
        p = shared / SYSTEM_DIR / "同期設定.yaml"
        if p.exists():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                rules.update(data.get("keep_in_vault") or {})
            except yaml.YAMLError:
                pass
    return rules


def is_heavy(path: Path, rules: dict) -> bool:
    name = path.name.lower()
    if name.endswith(".md"):
        return False
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in [str(x).lower() for x in rules.get("images", [])]:
        return False
    if ext == "pdf" and rules.get("pdf", True):
        return False
    if ext in [str(x).lower() for x in rules.get("video", [])]:
        return path.stat().st_size >= float(rules.get("video_max_mb", 20)) * 1024 * 1024
    return True


# ---------- リンクの形(F-18・F-19) ----------

def file_url(path: Path) -> str:
    p = path.as_posix()
    if p.startswith("//"):  # NAS などのネットワークの場所(\\nas\共有\...)は file://nas/共有/...
        return "file:" + quote(p, safe="/:")
    return "file:///" + quote(p.lstrip("/"), safe="/:")


def url_prefix(data_root: Path) -> str:
    return file_url(data_root).rstrip("/") + "/"


USERS_URL = re.compile(r"^file:///([A-Za-z]):/Users/[^/]+/", re.I)


def prefix_pattern(data_root: Path) -> re.Pattern:
    """自分の開発データの `file:///` の頭。`C:/Users/<名前>/...` なら <名前> は誰でもよいとする。

    1人が2台の PC を使い、Windows のユーザー名が PC ごとに違うと、共有クラウドフォルダの場所
    (C:/Users/<名前>/Box や C:/Users/<名前>/OneDrive)も違う。どちらの PC で書かれたリンクも同じ開発データとして読むため。"""
    pre = url_prefix(data_root)
    m = USERS_URL.match(pre)
    if not m:
        return re.compile(re.escape(pre), re.I)
    return re.compile(rf"file:///{m.group(1)}:/Users/[^/]+/" + re.escape(pre[m.end():]), re.I)


def to_shared(text: str, data_root: Path | None) -> str:
    """個人の `file:///<開発データ>/...` を `開発データ/...` にする。ほかの PC の場所で書かれたものも。"""
    if not data_root:
        return text
    pat = prefix_pattern(data_root)

    def repl(m: re.Match) -> str:
        dest = m.group(2)
        inner = dest[1:-1] if dest.startswith("<") else dest
        hit = pat.match(inner)
        if hit:
            rest = unquote(inner[hit.end():])
            new = DATA_PREFIX + rest
            new = f"<{new}>" if " " in new else new
            return m.group(0).replace(f"]({dest})", f"]({new})")
        return m.group(0)

    return MDLINK.sub(repl, text)


def to_personal(text: str, data_root: Path | None) -> str:
    """共有の `開発データ/...` を、自分の PC の `file:///` にする。"""
    if not data_root:
        return text

    def repl(m: re.Match) -> str:
        dest = m.group(2)
        inner = dest[1:-1] if dest.startswith("<") else dest
        if inner.startswith(DATA_PREFIX):
            new = file_url(data_root / inner[len(DATA_PREFIX):])
            return m.group(0).replace(f"]({dest})", f"]({new})")
        return m.group(0)

    return MDLINK.sub(repl, text)


# ---------- ノートのリンクを書き換える ----------

def relink(text: str, note_id: str, rel_name: str, new_url: str, own_note: bool,
           old_url: str | None = None) -> str:
    """添付 `_仕組み/attachments/<id>/<rel_name>` を指すリンクを `[名前](new_url)` にする。
    own_note(その id のノート)なら、ファイル名だけのリンクも対象にする。old_url を指すリンクも直す。"""
    tail = f"attachments/{note_id}/{rel_name}"
    shown = rel_name.split("/")[-1]

    def hits(target: str) -> bool:
        t = unquote(target.strip()).replace("\\", "/")
        return t.endswith(tail) or (own_note and t == rel_name)

    def wiki(m: re.Match) -> str:
        if not hits(m.group(1)):
            return m.group(0)
        alias = m.group(3)[1:] if m.group(3) else shown
        return f"[{alias}]({new_url})"

    def md(m: re.Match) -> str:
        dest = m.group(2)
        inner = dest[1:-1] if dest.startswith("<") else dest
        if hits(inner) or (old_url and inner == old_url):
            return f"[{m.group(1) or shown}]({new_url})"
        return m.group(0)

    return MDLINK.sub(md, WIKI.sub(wiki, text))


def free_name(dest: Path) -> Path:
    """同じ名前があれば _2、_3 … をつける。"""
    if not dest.exists():
        return dest
    stem, dot, ext = dest.name.rpartition(".")
    if not dot:
        stem, ext = dest.name, ""
    n = 2
    while True:
        cand = dest.with_name(f"{stem}_{n}.{ext}" if ext else f"{stem}_{n}")
        if not cand.exists():
            return cand
        n += 1


def is_private_note(fm: dict, rel: str) -> bool:
    """共有しないノートか(F-17c)。visibility PIP(古い 個人)、type メモ、00_PIP/(古い 00_日誌/)の中のノート。"""
    if vis.is_pip(fm):
        return True
    return rel.split("/", 1)[0] in (DIARY_TOP, OLD_DIARY_TOP)


def shared_folder_of(shared: Path | None, note_id: str) -> str | None:
    """共有 vault でのノートの一番上のフォルダ(プロジェクト名か 共通)。共有していなければ None。"""
    if not shared or not shared.exists():
        return None
    for p, rel in iter_md(shared):
        if ids.split_filename(p.stem)[0] == note_id and len(rel.parts) > 1:
            top = rel.parts[0]
            if top not in ("99_archive", "00_inbox", "00_週報"):
                return top
    return None


class Mover:
    def __init__(self, personal: Path, shared: Path | None, data_root: Path | None, member: str,
                 report: Report, backup: Backup, dry_run: bool, now: float, idle_seconds: int, me: str = "",
                 private_root: Path | None = None):
        self.personal = personal
        self.shared = shared
        self.data_root = data_root
        self.private_root = private_root  # 自分だけが見られる置き場所(F-17c)
        self.waiting = {"data": 0, "private": 0}  # 置き場所がなくて vault に残した重い添付の数
        self.member = member  # 開発データ/個人/<名前>/ の名前
        self.me = me or member  # 自分のノートか見分ける(番号_名前)
        self.report = report
        self.backup = backup
        self.dry_run = dry_run
        self.now = now
        self.idle_seconds = idle_seconds
        self.rules = keep_rules(shared)
        self._notes: list[tuple[Path, str]] | None = None
        self._private: set[str] | None = None
        self._known: set[str] = set()
        self._tops: dict[str, str] | None = None

    def busy(self, path: Path) -> bool:
        return self.idle_seconds > 0 and path.exists() and self.now - path.stat().st_mtime < self.idle_seconds

    def notes(self) -> list[tuple[Path, str]]:
        if self._notes is None:
            self._notes = [(p, rel.as_posix()) for p, rel in iter_md(self.personal)
                           if not theirs_file(p, self.me)]  # 他の人のノートは書き換えない
        return self._notes

    def private_ids(self) -> set[str]:
        """共有しないノートの id(F-17c)。自分の vault の中の、他の人のノートも含めて見る。"""
        if self._private is None:
            found, known = set(), set()
            for p, rel in iter_md(self.personal):
                file_id = ids.split_filename(p.stem)[0]
                text = read(p)
                head = frontmatter.split(text)[0] or ""
                if ("個人" not in head and "PIP" not in head and "メモ" not in head
                        and rel.parts[0] not in (DIARY_TOP, OLD_DIARY_TOP)):
                    if file_id:
                        known.add(file_id)
                    continue  # 属性欄を読むまでもなく共有するノート(同期を遅くしないため)
                fm = frontmatter.load(text)
                fm_id = str(fm.get("id") or "").strip().upper()
                these = {x for x in (file_id, fm_id) if x}
                known |= these
                if is_private_note(fm, rel.as_posix()):
                    found |= these
            self._private, self._known = found, known
        return self._private

    def shared_note_here(self, note_id: str) -> bool:
        """自分の vault に、共有するノートとしてあるか。消したノートの添付を、チームが見られる場所へ出さないため。"""
        self.private_ids()
        return note_id.upper() in self._known and not self.is_private(note_id)

    def is_private(self, note_id: str) -> bool:
        return note_id == DIARY_DIR or note_id.upper() in self.private_ids()

    def rewrite_links(self, note_id: str, rel_name: str, new_url: str, old_url: str | None = None) -> bool:
        """リンクを書き換える。書いている途中のノートがあれば何もしないで False。"""
        changes = []
        for p, rel in self.notes():
            own = ids.split_filename(p.stem)[0] == note_id
            text = read(p)
            new = relink(text, note_id, rel_name, new_url, own, old_url)
            if new != text:
                if self.busy(p):
                    return False
                changes.append((p, rel, new))
        for p, rel, new in changes:
            self.report.record(f"リンクを書き換えた: {rel}({rel_name.split('/')[-1]})")
            if not self.dry_run:
                self.backup.save(self.personal, p)
                write(p, new)
        return True

    def shared_top(self, note_id: str) -> str | None:
        """共有 vault でのノートの一番上のフォルダ(shared_folder_of と同じ。共有 vault を1回だけ見る)。"""
        if self._tops is None:
            self._tops = {}
            if self.shared and self.shared.exists():
                for p, rel in iter_md(self.shared):
                    nid = ids.split_filename(p.stem)[0]
                    if nid and len(rel.parts) > 1 and rel.parts[0] not in ("99_archive", "00_inbox", "00_週報"):
                        self._tops.setdefault(nid, rel.parts[0])
        return self._tops.get(note_id)

    def place_for(self, note_id: str, private: bool) -> Path | None:
        """重い添付の行き先。置き場所が設定にない(見つからない)ときは None。"""
        if private:
            return self.private_root / note_id if self.private_root else None
        if not self.data_root:
            return None
        top = self.shared_top(note_id)
        if top:
            return self.data_root / top / note_id
        return self.data_root / PERSONAL_DIR / self.member / note_id

    def shown(self, path: Path) -> str:
        """レポートに書く場所。開発データ/… か 自分用/…"""
        for root, label in ((self.data_root, "開発データ"), (self.private_root, "自分用")):
            if root:
                try:
                    return f"{label}/{path.relative_to(root).as_posix()}"
                except ValueError:
                    pass
        return str(path)

    def move_file(self, src: Path, dest: Path) -> Path | None:
        if dest.exists() and digest(dest) == digest(src):
            final = dest  # もう同じものがある(前回、移したあとで止まったなど)
        else:
            final = free_name(dest)
        if not self.dry_run:
            final.parent.mkdir(parents=True, exist_ok=True)
            if final == dest and dest.exists():
                src.unlink()
            else:
                shutil.move(str(src), str(final))
        return final

    def run(self) -> None:
        base = self.personal / ATTACH
        dirs = sorted(d for d in base.iterdir() if d.is_dir()) if base.exists() else []
        for note_dir in dirs:
            note_id = note_dir.name
            private = self.is_private(note_id)
            dest_dir = self.place_for(note_id, private)
            for f in sorted(note_dir.rglob("*")):
                if not f.is_file() or any(is_hidden(x) for x in f.relative_to(note_dir).parts):
                    continue
                if sync_copy_of(f)[0] or not is_heavy(f, self.rules):
                    continue
                if dest_dir is None:
                    self.waiting["private" if private else "data"] += 1
                    continue
                if self.busy(f):
                    self.report.record(f"{ATTACH}/{note_id}/{f.name} はコピー中かもしれないので、次の同期で移します")
                    continue
                rel_name = f.relative_to(note_dir).as_posix()
                target = dest_dir / rel_name
                final = free_name(target) if not (target.exists() and digest(target) == digest(f)) else target
                url = file_url(final)
                if not self.rewrite_links(note_id, rel_name, url):
                    self.report.later(f"{ATTACH}/{note_id}/{rel_name} を指すノートが書いている途中なので、次の同期で移します")
                    continue
                self.move_file(f, target)
                self.report.record(f"重い添付を移した: {ATTACH}/{note_id}/{rel_name} → {self.shown(final)}")
            self.promote(note_id, private)
        self.retarget()

    def retarget(self) -> None:
        """vault からもう移した添付の置き場所を、共有する・しないの変化に合わせる(F-17c)。"""
        personal_dir = self.data_root / PERSONAL_DIR / self.member if self.data_root else None
        if self.private_root and self.private_root.exists():
            for d in sorted(x for x in self.private_root.iterdir() if x.is_dir() and not is_hidden(x.name)):
                if self.shared_note_here(d.name):
                    dest = self.place_for(d.name, False)
                    if dest:
                        self.relocate(d.name, d, dest, "共有するノートになったので添付を移した")
        if personal_dir and personal_dir.exists() and self.private_root:
            for d in sorted(x for x in personal_dir.iterdir() if x.is_dir() and not is_hidden(x.name)):
                if self.is_private(d.name):
                    self.relocate(d.name, d, self.private_root / d.name, "共有しないノートなので添付を自分用へ移した")
        if personal_dir and personal_dir.exists():
            for d in sorted(x for x in personal_dir.iterdir() if x.is_dir() and not is_hidden(x.name)):
                if not self.is_private(d.name):
                    self.promote(d.name, False)

    def promote(self, note_id: str, private: bool = False) -> None:
        """F-20: 共有されたノートの添付を、_個人/ からプロジェクトのフォルダへ移す。"""
        if private or not self.data_root:
            return
        src_dir = self.data_root / PERSONAL_DIR / self.member / note_id
        top = self.shared_top(note_id)
        if not top or not src_dir.exists():
            return
        self.relocate(note_id, src_dir, self.data_root / top / note_id, "共有されたので添付を移した")

    def relocate(self, note_id: str, src_dir: Path, dest_dir: Path, what: str) -> None:
        """src_dir の中を dest_dir へ移し、リンクを書き換える。"""
        if not src_dir.exists() or src_dir == dest_dir:
            return
        for f in sorted(src_dir.rglob("*")):
            if not f.is_file():
                continue
            rel_name = f.relative_to(src_dir).as_posix()
            target = dest_dir / rel_name
            final = free_name(target) if not (target.exists() and digest(target) == digest(f)) else target
            if not self.rewrite_links(note_id, rel_name, file_url(final), old_url=file_url(f)):
                self.report.later(f"{self.shown(src_dir)} を指すノートが書いている途中なので、次の同期で移します")
                return
            self.move_file(f, target)
            self.report.record(f"{what}: {self.shown(f)} → {self.shown(final)}")


def _inside(a: Path, b: Path) -> bool:
    """a が b の下にあるか(同じ場所は含まない)。"""
    ka, kb = (os.path.normcase(os.path.normpath(str(x))) for x in (a, b))
    return ka != kb and ka.startswith(kb.rstrip("\\/") + os.sep)


def _same_place(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def follow_private_change(personal: Path, old: Path, new: Path, report: Report, backup: Backup,
                          dry_run: bool, now: float, idle_seconds: int, me: str) -> bool:
    """private_data を書き換えたとき、前のフォルダの添付をすべて新しいフォルダへコピーし、
    ノートのリンクを新しい場所に直す。前のフォルダは消さない。
    終わったら True。書いている途中のノートがあれば何もせず False(次の同期でやり直す)。"""
    files = [f for f in sorted(old.rglob("*")) if f.is_file()
             and not any(is_hidden(x) for x in f.relative_to(old).parts)]
    plan: dict[str, Path] = {}  # 前の場所からのパス → 新しい場所のファイル
    for f in files:
        rel = f.relative_to(old).as_posix()
        target = new / rel
        plan[rel] = target if (not target.exists() or digest(target) == digest(f)) else free_name(target)
    old_pat = prefix_pattern(old)

    def fix(text: str) -> str:
        def repl(m: re.Match) -> str:
            dest = m.group(2)
            inner = dest[1:-1] if dest.startswith("<") else dest
            hit = old_pat.match(inner)
            if not hit:
                return m.group(0)
            to = plan.get(unquote(inner[hit.end():]))
            if not to:
                return m.group(0)
            return m.group(0).replace(f"]({dest})", f"]({file_url(to)})")
        return MDLINK.sub(repl, text)

    changes = []
    for p, rel in iter_md(personal):
        if theirs_file(p, me):
            continue
        text = read(p)
        new_text = fix(text)
        if new_text != text:
            if idle_seconds > 0 and now - p.stat().st_mtime < idle_seconds:
                report.later(f"自分用の添付の場所を変えたのでリンクを直しますが、{rel.as_posix()} を書いている途中なので次の同期でやります")
                return False
            changes.append((p, rel, new_text))
    for rel, to in plan.items():
        if not dry_run and not to.exists():
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old / rel, to)
    for p, rel, new_text in changes:
        report.record(f"リンクを書き換えた: {rel.as_posix()}(自分用の添付の場所を変えたため)")
        if not dry_run:
            backup.save(personal, p)
            write(p, new_text)
    report.record(f"自分用の添付の場所を変えたので、{len(plan)} 件を {old} から {new} へコピーした(前のフォルダは残してあります。"
                  "確かめたら消してかまいません)")
    return True


def move_heavy(personal: Path, shared: Path | None, data_root: Path | None, member: str,
               report: Report, backup: Backup, dry_run: bool, now: float, idle_seconds: int,
               me: str = "", private_root: Path | None = None, private_mark: Path | None = None) -> None:
    data_missing = bool(data_root and not data_root.exists())
    if data_missing:
        report.warn(f"開発データのフォルダが見つかりません: {data_root}(同期アプリ(Box Drive・OneDrive など)が止まっていないか確かめてください)。"
                    "共有するノートの重い添付は移していません")
        data_root = None
    private_missing = False
    if private_root and not private_root.exists():
        if dry_run or not private_root.parent.exists():
            report.warn(f"自分用の添付のフォルダが見つかりません: {private_root}(同期アプリが止まっていないか確かめてください)。"
                        "共有しないノートの重い添付は移していません")
            private_root, private_missing = None, True
        else:
            private_root.mkdir()
            report.record(f"自分用の添付のフォルダを作った: {private_root}")
    # private_data を書き換えたら、前のフォルダの添付を新しいフォルダへコピーしてリンクを直す
    if private_root and private_mark:
        try:
            before = private_mark.read_text(encoding="utf-8").strip()
        except OSError:
            before = ""
        done = True
        if before and not _same_place(Path(before), private_root):
            old = Path(before)
            nested = _inside(old, private_root) or _inside(private_root, old)
            if old.is_dir() and not nested:
                done = follow_private_change(personal, old, private_root, report, backup, dry_run, now,
                                             idle_seconds, me or member)
            else:
                why = (f"新しい場所 {private_root} と前の場所 {old} が入れ子になっている" if nested
                       else f"前の自分用の添付のフォルダ {old} が見つからない")
                report.todo(f"自分用の添付の場所を変えましたが、{why}ので、コピーもリンクの書き換えもしていません。"
                            f"別々のフォルダにするか、前の場所に戻してください(コピーしなくてよければ {private_mark} を消す)")
                done = False
        if done and not dry_run and before != str(private_root):
            private_mark.parent.mkdir(parents=True, exist_ok=True)
            private_mark.write_text(str(private_root) + "\n", encoding="utf-8")
    m = Mover(personal, shared, data_root, member, report, backup, dry_run, now, idle_seconds, me, private_root)
    m.run()
    if m.waiting["data"] and not data_missing:
        report.todo(f"開発データの場所が設定にありません: 重い添付が {m.waiting['data']} 件 {ATTACH}/ にたまっています。"
                    "個人設定に shared_data を書いてください")
    if m.waiting["private"] and not private_missing:
        report.todo(f"自分用の添付の場所が設定にありません: 共有しないノートの重い添付が {m.waiting['private']} 件 {ATTACH}/ に"
                    "たまっています(開発データ/ はチーム全員が見られるので移していません)。"
                    "個人設定に private_data(自分だけが見られるフォルダ)を書いてください")
