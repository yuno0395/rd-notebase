"""F-47: 共有へ集めるノードの名前か別名が、共有の別のノードと重なったときに聞き、まとめる。

同期レポートに2つのチェックボックスを出す。

- [ ] 同じもの: [[自分のノード]] を [[共有のノード]] にまとめる
- [ ] 別もの: [[自分のノード]] と [[共有のノード]] は別のノードとして共有する

次の同期で、チェックのついた方を行う。答えは前回同期の記録(state)に残すので、二度は聞かない。
まとめるときは、名前と別名を aliases に、書いた人を author に足し、本文は末尾の章に入れて
「書き直す」タスクを置く。自分の vault のリンクは付け替え、自分のノードは 99_archive へ移す(消さない)。
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta

from . import frontmatter, ids
from .assign import LINK
from .report import REPORT_NAME
from .share import ARCHIVE, Context, Item, as_list, note_stem, recent
from .vault import iter_md, read, theirs_file, write

CHOICE_LINE = re.compile(r"^-\s*\[[xX]\]\s*(同じもの|別もの):\s*(.*)$")
SAME, OTHER = "同じもの", "別もの"
REWRITE_DAYS = 7


def names_of(item: Item) -> set[str]:
    return {n.strip().lower() for n in [item.name, *as_list(item.fm.get("aliases"))] if n.strip()}


def ids_in(text: str) -> list[str]:
    out = []
    for m in LINK.finditer(text):
        file_id, _ = ids.split_filename(m.group(1).strip().split("/")[-1])
        if file_id:
            out.append(file_id)
    return out


def read_choices(ctx: Context) -> dict[tuple[str, str], set[str]]:
    """前回の同期レポートで、チェックのついた答え。{(自分の id, 共有の id): {"同じもの" か "別もの"}}"""
    path = ctx.personal / REPORT_NAME
    out: dict[tuple[str, str], set[str]] = {}
    if not path.exists():
        return out
    for line in read(path).splitlines():
        m = CHOICE_LINE.match(line.strip())
        if not m:
            continue
        found = ids_in(m.group(2))
        if len(found) >= 2:
            out.setdefault((found[0], found[1]), set()).add(m.group(1))
    return out


def link_of(item: Item) -> str:
    return f"[[{note_stem(item.filename)}|{item.name}]]"


def lines_for(item: Item, other: Item) -> tuple[str, str]:
    theirs = f"{link_of(other)}({other.author or '作成者不明'})"
    return (f"{SAME}: {link_of(item)} を {theirs} にまとめる(チェックすると、次の同期でまとめます)",
            f"{OTHER}: {link_of(item)} と {theirs} は別のノートとして共有する")


def flow(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in values) + "]"


def demote(body: str) -> str:
    """本文の見出しを1段下げ、中身のない見出し(テンプレートのまま)を除く。"""
    lines = body.strip("\n").splitlines()
    kept = []
    for i, line in enumerate(lines):
        if re.match(r"^#{1,6} ", line):
            rest = next((x for x in lines[i + 1:] if x.strip()), None)
            if rest is None or re.match(r"^#{1,6} ", rest) and len(rest) - len(rest.lstrip("#")) <= len(line) - len(line.lstrip("#")):
                continue
            line = "#" + line if not line.startswith("######") else line
        kept.append(line)
    return "\n".join(kept).strip("\n")


def merge_into(ctx: Context, item: Item, other: Item) -> bool:
    """item(自分のノード)を other(共有のノード)にまとめる。書いている途中なら次に回す(False)。"""
    if recent(ctx, other.path) or recent(ctx, item.path):
        return False
    stamp = datetime.fromtimestamp(ctx.now, tz=ids.JST)
    day = stamp.strftime("%Y-%m-%d")
    due = (stamp + timedelta(days=REWRITE_DAYS)).strftime("%Y-%m-%d")
    who = item.author or ctx.member
    o_stem = note_stem(other.filename)

    # 共有のノード: aliases と author を足し、本文を末尾の章に入れる
    t_text = read(other.path)
    fm = frontmatter.load(t_text)
    aliases = as_list(fm.get("aliases"))
    if other.name.lower() not in {a.lower() for a in aliases}:
        aliases.insert(0, other.name)
    for n in [item.name, *as_list(item.fm.get("aliases"))]:
        if n.strip() and n.strip().lower() not in {a.lower() for a in aliases}:
            aliases.append(n.strip())
    authors = as_list(fm.get("author"))
    if who not in authors:
        authors.append(who)
    nl = frontmatter.newline_of(t_text)
    new = frontmatter.set_values(t_text, {"aliases": flow(aliases),
                                          "author": flow(authors) if len(authors) > 1 else authors[0]})
    body = demote(frontmatter.split(item.text)[1])
    section = [f"## まとめたメモ({item.name}、{who}、{day})",
               f"- [ ] {who}: 「{item.name}」のメモを上の本文に書き直して、この章を消す 📅 {due}"]
    if body:
        section += ["", body]
    new = new.rstrip("\r\n") + nl + nl + nl.join(section).replace("\n", nl) + nl

    # 自分の vault で item を指していたリンク(他の人のノートと 99_archive は除く)
    def repl(m: re.Match) -> str:
        target = m.group(1).strip()
        if ids.split_filename(target.split("/")[-1])[0] != item.id:
            return m.group(0)
        shown = m.group(2)[1:] if m.group(2) else item.name
        return f"[[{o_stem}|{shown}]]"

    relinked = []
    for path, rel in iter_md(ctx.personal):
        if rel.parts[0] == ARCHIVE or path == item.path or theirs_file(path, ctx.member):
            continue
        text = read(path)
        changed = LINK.sub(repl, text)
        if changed != text:
            relinked.append((path, changed))

    pdir = ctx.personal / "_仕組み/attachments" / item.id
    sdir = ctx.shared / "_仕組み/attachments" / other.id
    attachments = [f for f in pdir.rglob("*") if f.is_file()] if pdir.exists() else []

    ctx.report.record(f"まとめた: {item.rel} を 共有/{other.rel} にまとめ、「{item.name}」を別名に足しました。"
                      f"書き直しのタスクを入れています")
    for path, _ in relinked:
        ctx.report.record(f"リンクを付け替えた: {path.relative_to(ctx.personal).as_posix()}"
                          f"({item.name} → {other.name})")
    ctx.count("統合")
    if ctx.dry_run:
        return True

    ctx.backup.save(ctx.shared, other.path)
    write(other.path, new)
    for f in attachments:
        dest = sdir / f.relative_to(pdir)
        if dest.exists():
            ctx.report.warn(f"添付: {dest.relative_to(ctx.shared).as_posix()} がすでにあるので、"
                            f"{f.relative_to(ctx.personal).as_posix()} はコピーしていません")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    for path, changed in relinked:
        ctx.backup.save(ctx.personal, path)
        write(path, changed)
    archived = ctx.personal / ARCHIVE / item.filename
    archived.parent.mkdir(parents=True, exist_ok=True)
    ctx.backup.save(ctx.personal, item.path)
    write(archived, frontmatter.set_values(item.text, {"merged_into": json.dumps(f"[[{o_stem}|{other.name}]]", ensure_ascii=False)}))
    item.path.unlink()
    ctx.state.set(f"merge:{item.id}", {"into": other.id})
    return True


def check_duplicates(ctx: Context, item: Item, candidates: list[Item],
                     choices: dict[tuple[str, str], set[str]]) -> bool:
    """まだ共有していないノードの重なりを調べる。集めるのを止めるときは True。"""
    mine = names_of(item)
    hits = [o for o in candidates if o.id != item.id and names_of(o) & mine]
    if not hits:
        return False
    key = f"merge:{item.id}"
    keep = set((ctx.state.get(key) or {}).get("keep", []))
    for o in hits:
        picked = choices.get((item.id, o.id), set())
        same_line, other_line = lines_for(item, o)
        if picked == {SAME}:
            if not merge_into(ctx, item, o):
                ctx.report.record(f"{item.rel} か 共有/{o.rel} が書いている途中なので、まとめるのは次の同期に回します")
                ctx.report.todo(same_line, checked=True)
                ctx.report.todo(other_line)
            elif ctx.dry_run:
                ctx.report.todo(same_line, checked=True)  # 答えを消さない
                ctx.report.todo(other_line)
            return True
        if picked == {SAME, OTHER}:
            ctx.report.warn(f"{link_of(item)} と {link_of(o)} の「同じもの」と「別もの」の両方にチェックがあります。"
                            "どちらか1つにしてください")
        elif picked == {OTHER}:
            keep.add(o.id)
            if ctx.dry_run:
                ctx.report.todo(same_line)
                ctx.report.todo(other_line, checked=True)
    if keep:
        ctx.state.set(key, {"keep": sorted(keep)})
    waiting = [o for o in hits if o.id not in keep]
    for o in waiting:
        same_line, other_line = lines_for(item, o)
        ctx.report.todo(same_line)
        ctx.report.todo(other_line)
        ctx.asked.add(frozenset((item.id, o.id)))
    return bool(waiting)


def quiet_same_names(ctx: Context) -> None:
    """F-04 の「同じ名前」のうち、ここで聞いているもの・答えが出たものは出さない。"""
    fine = set(ctx.asked)
    merged = set()
    for k, rec in ctx.state.starting("merge:").items():
        mine = k.split(":", 1)[1]
        for o in rec.get("keep", []):
            fine.add(frozenset((mine, o)))
        if rec.get("into"):
            merged.add(mine)

    def settled(todo: str) -> bool:
        if not todo.startswith("同じ名前:"):
            return False
        found = [i for i in dict.fromkeys(ids_in(todo)) if i not in merged]
        if len(found) < 2:
            return True
        return all(frozenset((a, b)) in fine for n, a in enumerate(found) for b in found[n + 1:])

    ctx.report.todos = [t for t in ctx.report.todos if not settled(t)]
