"""F-05〜11、F-14、F-15: 共有 vault へ集め(集約)、各自の 90_共有/ へ配る(再配布)。

前回同期したときの内容のハッシュを覚えておき(state.py)、3つを見比べて決める。

| 個人側 | 共有側 | 自分のノート(01〜05)        | 配られたノート(90_共有/)        |
| ------ | ------ | ---------------------------- | ------------------------------- |
| 変わった | そのまま | 共有へコピー(集約)          | 編集しないよう知らせる          |
| そのまま | 変わった | 個人へコピー(他の人の書き足し) | 90_共有/ へコピー(再配布)     |
| 変わった | 変わった | 競合ファイルを置いて知らせる  | 共有に合わせる(元は backup へ)  |

ファイルを消すことはしない。99_archive への移動だけを共有へ反映する(F-09)。
"""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import frontmatter, ids
from .assign import LINK
from .report import Report
from .safety import Backup
from .heavy import DEFAULT_KEEP, is_heavy, to_personal, to_shared
from .state import State, digest, digest_text
from .vault import SKIP_DIRS, box_copy_of, is_hidden, read, write

OWN_DIRS = ("01_目的", "02_ノード", "03_イシュー", "04_タスク", "05_ナレッジ")
DIST = "90_共有"
ARCHIVE = "99_archive"
COMMON = "共通"
# 共有 vault の一番上で、プロジェクトのフォルダではないもの
SHARED_SYSTEM = SKIP_DIRS | {"00_inbox", "00_週報", ARCHIVE}
BIG_IMPACT = {"方針", "絞込", "出荷", "大"}  # 「大」は v0.22 までの書き方
TYPE_DIR = {"目的": "01_目的", "仮説": "01_目的", "ノード": "02_ノード",
            "イシュー": "03_イシュー", "タスク": "04_タスク"}
CONFLICT_MARK = "_競合_"
WINDOW = "窓口"           # 機密の窓口(機密フォルダごとに1つ。見てよい人と社内の当事者だけを書く)
WINDOW_DIR = "機密の窓口"
MD_LINK = re.compile(r"\]\(([^)\s]+)")


@dataclass
class Item:
    """1つのノート(拡張子 .md、図の .excalidraw.md も含む)。"""
    root: Path
    rel: str          # vault の一番上からの相対パス(/ 区切り)
    id: str
    name: str
    fm: dict
    text: str

    @property
    def path(self) -> Path:
        return self.root / self.rel

    @property
    def top(self) -> str:
        return self.rel.split("/")[0]

    @property
    def type(self) -> str:
        return str(self.fm.get("type") or "").strip()

    @property
    def authors(self) -> list[str]:
        """書いた人。まとめたノードは [佐藤, Yu] のように並ぶ(先頭が最初に書いた人)。"""
        return [plain_name(a).strip() for a in as_list(self.fm.get("author")) if a.strip()]

    @property
    def author(self) -> str:
        a = self.authors
        return a[0] if a else ""

    @property
    def filename(self) -> str:
        return self.rel.split("/")[-1]


def note_stem(filename: str) -> str:
    for ext in (".excalidraw.md", ".md"):
        if filename.endswith(ext):
            return filename[: -len(ext)]
    return filename


def scan(root: Path, tops: tuple[str, ...] | None = None, skip_tops: set[str] = frozenset()) -> dict[str, list[Item]]:
    """id つきのノートを {id: [Item]} で返す。競合ファイルは数えない。"""
    out: dict[str, list[Item]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        parts = rel.parts
        if len(parts) < 2 or any(is_hidden(x) for x in parts):
            continue
        if tops is not None and parts[0] not in tops:
            continue
        if parts[0] in skip_tops:
            continue
        stem = note_stem(p.name)
        if CONFLICT_MARK in stem or box_copy_of(p)[0]:
            continue
        file_id, name = ids.split_filename(stem)
        if not file_id:
            continue
        text = read(p)
        out.setdefault(file_id, []).append(
            Item(root, rel.as_posix(), file_id, name, frontmatter.load(text), text))
    return out


def as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None and str(x).strip()]
    return [str(value)]


def link_targets(value) -> list[str]:
    """属性の値から [[ ]] の行き先(| の左)を取り出す。リンクでなければ値そのもの。"""
    out = []
    for v in as_list(value):
        found = [m.group(1).strip() for m in LINK.finditer(v)]
        out += found or [v.strip()]
    return out


def plain_name(value: str) -> str:
    """[[0RAYFN001_Yu|Yu]] や Yu を、名前 Yu にする。"""
    t = link_targets(value)
    t = t[0] if t else value
    return ids.split_filename(t)[1] if ids.split_filename(t)[0] else t


@dataclass
class Context:
    member: str
    personal: Path
    shared: Path
    secret: list[Path]
    report: Report
    backup: Backup
    state: State
    dry_run: bool
    now: float
    idle_seconds: int
    data_root: Path | None = None  # 開発データ(F-19 のリンクの書き換えに使う)
    keep: dict = field(default_factory=lambda: dict(DEFAULT_KEEP))  # vault に残す添付の決まり(F-17)
    by_id: dict[str, Item] = field(default_factory=dict)      # 行き先を調べるための全ノート
    by_name: dict[str, set[str]] = field(default_factory=dict)  # 名前(小文字)→ id
    projects: dict[str, Item] = field(default_factory=dict)   # プロジェクト名 → 台帳
    secret_names: set[str] = field(default_factory=set)
    secret_words: set[str] = field(default_factory=set)       # 機密フォルダと事実ノートの名前(小文字)
    counts: dict[str, int] = field(default_factory=dict)
    asked: set[frozenset] = field(default_factory=set)        # F-47 で聞いている組
    fresh: set[str] = field(default_factory=set)              # F-28: 作ったばかりでテンプレートのままのノート

    def count(self, what: str) -> None:
        self.counts[what] = self.counts.get(what, 0) + 1

    # ---------- 書き込み(試し運転では書かない) ----------

    def copy(self, src: Path, dest: Path, dest_root: Path) -> None:
        if self.dry_run:
            return
        self.backup.save(dest_root, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if self.data_root and src.name.endswith(".md"):
            # F-19: 共有では 開発データ/ からの相対パス、個人ではその PC の file:///
            text = read(src)
            text = to_shared(text, self.data_root) if dest_root == self.shared else to_personal(text, self.data_root)
            write(dest, text)
            shutil.copystat(src, dest)
        else:
            shutil.copy2(src, dest)

    def digest(self, path: Path) -> str:
        """中身のハッシュ。ノートは開発データへのリンクを共有の形にそろえてから比べる(F-19)。"""
        if self.data_root and path.name.endswith(".md"):
            return digest_text(to_shared(read(path), self.data_root))
        return digest(path)

    def move(self, src: Path, dest: Path) -> None:
        if self.dry_run:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)

    # ---------- 調べもの ----------

    def resolve(self, target: str) -> Item | None:
        file_id, _ = ids.split_filename(target.split("/")[-1])
        if file_id and file_id in self.by_id:
            return self.by_id[file_id]
        found = self.by_name.get(target.strip().lower(), set())
        if len(found) == 1:
            return self.by_id.get(next(iter(found)))
        return None

    def project_of(self, item: Item, seen: set[str] | None = None) -> str | None:
        """F-06: ノートの振り分け先のプロジェクト。共通なら "共通"。決まらなければ None。"""
        seen = seen or set()
        if item.id in seen:
            return None
        seen.add(item.id)
        t = item.type
        if t in ("ノード", WINDOW):
            return COMMON
        if t == "プロジェクト":
            return item.name
        if t in ("イシュー", "目的"):
            ps = [plain_name(p) for p in as_list(item.fm.get("project"))]
            if t == "イシュー" and (len(ps) > 1 or COMMON in ps):
                return COMMON
            return ps[0] if len(ps) == 1 else None
        for target in link_targets(item.fm.get("parent")):
            parent = self.resolve(target)
            if parent:
                p = self.project_of(parent, seen)
                if p:
                    return p
        return None

    def reaches_big_issue(self, item: Item, seen: set[str] | None = None) -> bool:
        """parent か risk_reduction をたどって impact 大のイシューに着くか。"""
        seen = seen or set()
        if item.id in seen:
            return False
        seen.add(item.id)
        if item.type == "イシュー":
            return str(item.fm.get("impact") or "").strip() in BIG_IMPACT
        targets = link_targets(item.fm.get("parent"))
        targets += [m.group(1).strip() for v in as_list(item.fm.get("risk_reduction"))
                    for m in LINK.finditer(v)]
        for t in targets:
            p = self.resolve(t)
            if p and self.reaches_big_issue(p, seen):
                return True
        return False

    def secret_leaks(self, item: Item) -> list[str]:
        """機密の窓口の全文と secret_refs に、機密フォルダか事実ノートの名前が入っていないか。"""
        if item.type == WINDOW:
            text = item.text
        else:
            text = "\n".join(as_list(item.fm.get("secret_refs")))
        low = text.lower()
        return sorted(w for w in self.secret_words if w in low)

    def bad_secret_refs(self, item: Item) -> list[str]:
        """secret_refs のうち、機密の窓口へのリンクでないもの。"""
        bad = []
        for v in as_list(item.fm.get("secret_refs")):
            targets = [m.group(1).strip() for m in LINK.finditer(v)]
            if not targets:
                bad.append(v.strip())
                continue
            for t in targets:
                found = self.resolve(t)
                if not found or found.type != WINDOW:
                    bad.append(t)
        return bad

    def secret_links(self, item: Item) -> list[str]:
        """F-40: 機密フォルダの中のファイルへのリンク・画像。"""
        hits = []
        for m in LINK.finditer(item.text):
            target = m.group(1).strip()
            last = target.split("/")[-1]
            key = note_stem(last).lower()
            if key in self.secret_names or last.lower() in self.secret_names:
                hits.append(target)
        for m in MD_LINK.finditer(item.text):
            target = m.group(1)
            if any(s.name in target for s in self.secret):
                hits.append(target)
        return hits


def destination(ctx: Context, item: Item) -> str | None:
    """共有 vault での置き場所(相対パス)。"""
    project = ctx.project_of(item)
    if project is None:
        return None
    folder = TYPE_DIR.get(item.type) or (item.top if item.top in OWN_DIRS else "")
    if item.type == "プロジェクト":
        return f"{project}/{item.filename}"
    if item.type == "ノード":
        return f"{COMMON}/02_ノード/{item.filename}"
    if item.type == WINDOW:
        return f"{COMMON}/{WINDOW_DIR}/{item.filename}"
    return f"{project}/{folder}/{item.filename}" if folder else f"{project}/{item.filename}"


def check_conditions(ctx: Context, item: Item) -> str | None:
    """集める条件(F-05)。満たさなければ理由を返す。visibility 個人は "" を返す(知らせない)。"""
    vis = str(item.fm.get("visibility") or "チーム").strip()
    if vis == "個人":
        return ""
    link = f"[[{note_stem(item.filename)}|{item.name}]]"
    if item.type == "ナレッジ":
        missing = [k for k in ("author", "reviewed_by", "risk_reduction", "usefulness")
                   if not as_list(item.fm.get(k))]
        if missing:
            return f"未入力: {link} の {'・'.join(missing)} が空です(共有していません)"
    if item.type == "ノード" and not item.author:
        return f"未入力: {link} の author が空です(共有していません)"
    if item.type in ("ナレッジ", "ナレッジ図", "結果") and ctx.reaches_big_issue(item):
        others = [r for r in (plain_name(x) for x in as_list(item.fm.get("reviewed_by")))
                  if r and r not in item.authors]
        if not others:
            return f"確認待ち: {link} は impact 大のイシューにつながるため、作成者以外の確認者が必要です(共有していません)"
    hits = ctx.secret_links(item)
    if hits:
        return (f"機密へのリンク: {link} に機密フォルダの中へのリンクがあります"
                f"({'、'.join(hits)})。secret_refs に機密の窓口へのリンクを書いてください(共有していません)")
    leaks = ctx.secret_leaks(item)
    if leaks:
        where = "本文か属性欄" if item.type == WINDOW else "secret_refs"
        return (f"機密へのリンク: {link} の {where} に、機密フォルダか事実ノートの名前({'、'.join(leaks)})が"
                "入っています。顧客名を使わない呼び名にしてください(共有していません)")
    bad = ctx.bad_secret_refs(item)
    if bad:
        ctx.report.todo(f"secret_refs: {link} の {'、'.join(bad)} は機密の窓口へのリンクではありません。"
                        "`[[案件A]]` のように、共有の 共通/機密の窓口/ のノートへのリンクにしてください")
    if ctx.project_of(item) is None:
        return f"project 不明: {link} の振り分け先が決まりません。project か parent を書いてください(共有していません)"
    project = ctx.project_of(item)
    if project != COMMON and item.type != "プロジェクト" and project not in ctx.projects:
        return f"project 不明: {link} のプロジェクト「{project}」の台帳が共有 vault にありません(共有していません)"
    return None


def conflict_path(path: Path, member: str, now: datetime) -> Path:
    name = path.name
    base, dot, ext = name.partition(".")
    return path.with_name(f"{base}{CONFLICT_MARK}{member}_{now.strftime('%Y%m%d-%H%M')}{dot}{ext}")


def recent(ctx: Context, path: Path) -> bool:
    """最後の保存から idle_seconds たっていない(書いている途中かもしれない)。"""
    # idle_seconds が 0 なら待たない(Windows ではファイルの時刻が今より少し先になることがある)
    return ctx.idle_seconds > 0 and path.exists() and time.time() - path.stat().st_mtime < ctx.idle_seconds


def sync_pair(ctx: Context, key: str, p: Path, s: Path, p_rel: str, s_rel: str,
              mode: str, label: str) -> None:
    """1組のファイルを見比べて同期する。mode は "both"(自分のもの)か "down"(配られたもの)。"""
    rec = ctx.state.get(key)
    last = rec.get("h") if rec else None
    pe, se = p.exists(), s.exists()
    if recent(ctx, p) or recent(ctx, s):
        ctx.report.record(f"{label} は書いている途中なので、次の同期に回します")
        return
    if not pe and not se:
        return
    if mode == "down" and not se:
        return

    def done(h: str) -> None:
        ctx.state.set(key, {"p": p_rel, "s": s_rel, "h": h})

    if pe and not se:  # 共有にまだない(消されていても、削除は反映しない)
        ctx.copy(p, s, ctx.shared)
        ctx.report.record(f"集約: {label} → 共有/{s_rel}")
        ctx.count("集約")
        return done(ctx.digest(p))
    if se and not pe:
        ctx.copy(s, p, ctx.personal)
        ctx.report.record(f"{'再配布' if mode == 'down' else '取り込み'}: 共有/{s_rel} → {p_rel}")
        ctx.count("再配布" if mode == "down" else "取り込み")
        return done(ctx.digest(s))

    hp, hs = ctx.digest(p), ctx.digest(s)
    if hp == hs:
        return done(hp)
    if mode == "down":
        if last is not None and hs == last:
            ctx.report.todo(f"90_共有 の編集: {p_rel} は次に共有が変わると上書きされます。"
                            "書き足すなら自分のフォルダ(01〜05)へ移してください")
            return
        ctx.copy(s, p, ctx.personal)
        if last is not None and hp != last:
            ctx.report.record(f"再配布: 共有/{s_rel} → {p_rel}(90_共有 での編集は backup に残しました)")
        else:
            ctx.report.record(f"再配布: 共有/{s_rel} → {p_rel}")
        ctx.count("再配布")
        return done(hs)

    if rec and "c" in rec:  # 前に競合した。人がまとめた側を正にする
        if hp == rec["c"] and hs != rec.get("cs"):
            ctx.copy(s, p, ctx.personal)
            ctx.report.record(f"競合の解消: 共有/{s_rel} でまとめた内容を {p_rel} に入れました")
            ctx.count("取り込み")
            return done(hs)
        if hs == rec.get("cs") and hp != rec["c"]:
            ctx.copy(p, s, ctx.shared)
            ctx.report.record(f"競合の解消: {p_rel} でまとめた内容を 共有/{s_rel} に入れました")
            ctx.count("集約")
            return done(hp)
    if last is not None and hs == last:      # 個人側だけ変わった
        ctx.copy(p, s, ctx.shared)
        ctx.report.record(f"集約: {label} → 共有/{s_rel}")
        ctx.count("集約")
        return done(hp)
    if last is not None and hp == last:      # 共有側だけ変わった(他の人の書き足し)
        ctx.copy(s, p, ctx.personal)
        ctx.report.record(f"取り込み: 共有/{s_rel} の変更を {p_rel} に入れました")
        ctx.count("取り込み")
        return done(hs)

    # 両方変わった、または前回の記録がなく中身が違う(F-14、F-15、F-34)
    stamp = datetime.fromtimestamp(ctx.now, tz=ids.JST)
    if rec and rec.get("c") == hp and rec.get("cs") == hs:
        cpath = ctx.shared / rec["cf"]   # まだまとめられていない
    else:
        cpath = conflict_path(s, ctx.member, stamp)
        if not ctx.dry_run:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            ctx.copy(p, cpath, ctx.shared)
        ctx.report.record(f"競合: {label} と 共有/{s_rel} の両方が変わっていたので、"
                          f"共有に {cpath.name} を置きました")
        ctx.count("競合")
    ctx.report.todo(f"競合: 共有/{s_rel} と自分の {p_rel} の両方が変わっています。"
                    f"共有の `{cpath.name}` を見て元のファイルにまとめ、競合ファイルは 99_archive へ移してください")
    new = dict(rec or {"p": p_rel, "s": s_rel})
    new.update({"p": p_rel, "s": s_rel, "c": hp, "cs": hs,
                "cf": cpath.relative_to(ctx.shared).as_posix()})
    if last is not None:
        new["h"] = last
    ctx.state.set(key, new)


def sync_attachments(ctx: Context, note_id: str, mode: str) -> None:
    """F-07: _仕組み/attachments/<id>/ を同じパスのまま同期する。ファイル名は変えない。"""
    pdir = ctx.personal / "_仕組み/attachments" / note_id
    sdir = ctx.shared / "_仕組み/attachments" / note_id
    rels = set()
    for d in (pdir, sdir):
        if d.exists():
            rels |= {f.relative_to(d).as_posix() for f in d.rglob("*")
                     if f.is_file() and not box_copy_of(f)[0] and not is_heavy(f, ctx.keep)}
    if mode == "down":
        rels = {r for r in rels if (sdir / r).exists()}
    for r in sorted(rels):
        rel = f"_仕組み/attachments/{note_id}/{r}"
        sync_pair(ctx, f"att:{note_id}/{r}", pdir / r, sdir / r, rel, rel, mode, rel)


def different(a: Item, b: Item) -> bool:
    return a.name != b.name or bool(a.author and b.author and a.author != b.author)


def my_projects(ctx: Context) -> set[str]:
    out = set()
    for name, item in ctx.projects.items():
        members = {plain_name(m) for m in as_list(item.fm.get("members"))}
        if ctx.member in members:
            out.add(name)
    return out


def build_index(ctx: Context, *groups: dict[str, list[Item]]) -> None:
    for g in groups:
        for i, items in g.items():
            ctx.by_id.setdefault(i, items[0])
            for it in items:
                for n in [it.name, *as_list(it.fm.get("aliases"))]:
                    ctx.by_name.setdefault(n.strip().lower(), set()).add(i)


def run_share(ctx: Context) -> None:
    from .merge import check_duplicates, quiet_same_names, read_choices

    mine = scan(ctx.personal, tops=OWN_DIRS + (ARCHIVE,))
    for items in mine.values():
        for it in items:
            # author は id 付けの手順で書く(試し運転ではまだ書いていない)
            it.fm.setdefault("author", ctx.member) if not it.author else None
    shared = scan(ctx.shared, skip_tops=SKIP_DIRS | {"00_inbox", "00_週報"})
    build_index(ctx, mine, shared)
    for items in shared.values():
        for it in items:
            if it.type == "プロジェクト" and it.top != ARCHIVE:
                ctx.projects[it.name] = it
    for sec in ctx.secret:
        if sec.exists():
            for p in sec.rglob("*"):
                if p.is_file() and not any(is_hidden(x) for x in p.relative_to(sec).parts):
                    ctx.secret_names.add(note_stem(p.name).lower())
                    ctx.secret_names.add(p.name.lower())
                    rel = p.relative_to(sec)
                    if p.suffix == ".md" and rel.parts[0] not in SKIP_DIRS and not p.name.startswith("00_"):
                        word = ids.split_filename(note_stem(p.name))[1].strip().lower()
                        if len(word) >= 2:
                            ctx.secret_words.add(word)
            if len(sec.name) >= 2:
                ctx.secret_words.add(sec.name.lower())
    choices = read_choices(ctx)
    shared_nodes = [items[0] for i, items in sorted(shared.items())
                    if i not in mine and len(items) == 1 and items[0].type == "ノード" and items[0].top != ARCHIVE]

    # ---------- 集約(自分のノート) ----------
    for note_id, items in sorted(mine.items()):
        if len(items) > 1:
            ctx.report.warn(f"同じ id: {note_id} のノートが個人 vault に {len(items)} つあります"
                            f"({'、'.join(i.rel for i in items)})。集めていません")
            continue
        item = items[0]
        key = f"note:{note_id}"
        rec = ctx.state.get(key)
        in_shared = shared.get(note_id, [])

        if item.top == ARCHIVE:  # F-09: 99_archive への移動を共有へ反映する
            if rec and not rec["s"].startswith(ARCHIVE + "/") and (ctx.shared / rec["s"]).exists():
                dest = f"{ARCHIVE}/{item.filename}"
                ctx.move(ctx.shared / rec["s"], ctx.shared / dest)
                ctx.report.record(f"99_archive へ移した: 共有/{rec['s']} → 共有/{dest}")
                ctx.count("移動")
                rec = dict(rec, s=dest)
                ctx.state.set(key, rec)
                if ctx.dry_run:
                    continue
            if rec:
                sync_pair(ctx, key, item.path, ctx.shared / rec["s"], item.rel, rec["s"], "both", item.rel)
            continue

        if note_id in ctx.fresh and not rec and not in_shared:
            ctx.report.record(f"作ったばかりでテンプレートのままなので、まだ集めていません: {item.rel}")
            continue

        reason = check_conditions(ctx, item)
        if reason is not None:
            if reason:
                ctx.report.todo(reason)
            continue

        # F-47: 初めて共有するノードの名前か別名が、共有の別のノードと重なれば聞く
        if item.type == "ノード" and not rec and not in_shared:
            if check_duplicates(ctx, item, shared_nodes, choices):
                continue

        dest = destination(ctx, item)
        if rec and (ctx.shared / rec["s"]).exists():
            current = rec["s"]
        else:
            # F-08: 同じ id で別のノート(作成者か名前が違う)があれば集めない
            clash = [o for o in in_shared if different(o, item)]
            if clash:
                o = clash[0]
                ctx.report.warn(
                    f"同じ id: {note_id} が共有の {o.rel}({o.author or '作成者不明'}「{o.name}」)にもあります。"
                    "人の記号の設定を確かめてください(集めていません)")
                continue
            current = in_shared[0].rel if in_shared else dest

        # 振り分け先が変わった(project や parent を直した)ら、共有のファイルを移す
        if current != dest and (ctx.shared / current).exists() and not current.startswith(ARCHIVE + "/"):
            if rec and ctx.digest(ctx.shared / current) == rec.get("h"):
                ctx.move(ctx.shared / current, ctx.shared / dest)
                ctx.report.record(f"振り分け直し: 共有/{current} → 共有/{dest}")
                ctx.count("移動")
                if ctx.dry_run:
                    continue
                current = dest
            else:
                ctx.report.todo(f"振り分け: {item.rel} の行き先が 共有/{dest} に変わりましたが、"
                                f"共有/{current} も変わっているので移していません")
        sync_pair(ctx, key, item.path, ctx.shared / current, item.rel, current, "both", item.rel)
        sync_attachments(ctx, note_id, "both")

    # ---------- 再配布(他の人のノート) ----------
    projects = my_projects(ctx) | {COMMON}
    mine_ids = set(mine)
    for note_id, items in sorted(shared.items()):
        if note_id in mine_ids:
            continue  # F-11: 自分のフォルダに同じ id があれば配らない(違いは上の競合で知らせる)
        if len(items) > 1:
            ctx.report.warn(f"同じ id: {note_id} のノートが共有 vault に {len(items)} つあります"
                            f"({'、'.join(i.rel for i in items)})。配っていません")
            continue
        item = items[0]
        key = f"note:{note_id}"
        rec = ctx.state.get(key)
        if item.author == ctx.member:
            continue  # F-10: 自分が書いたノートは配らない
        if item.top == ARCHIVE:
            if not rec:
                continue  # 配っていなかったものは、archive に入ってからは配らない
        elif item.top not in projects:
            continue
        p_rel = f"{DIST}/{item.rel}"
        if rec and rec.get("p") != p_rel and (ctx.personal / rec["p"]).exists():
            ctx.move(ctx.personal / rec["p"], ctx.personal / p_rel)
            ctx.report.record(f"再配布: 共有で移されたので {rec['p']} → {p_rel}")
            if ctx.dry_run:
                continue
        sync_pair(ctx, key, ctx.personal / p_rel, item.path, p_rel, item.rel, "down", p_rel)
        sync_attachments(ctx, note_id, "down")

    quiet_same_names(ctx)
    if ctx.counts:
        summary = " / ".join(f"{k} {v}件" for k, v in ctx.counts.items())
        ctx.report.record(f"集約と再配布: {summary}")
