"""F-62: 別の Obsidian の vault からノートと添付を個人 vault へ取り込む(仕様書「別の Obsidian から取り込む」v0.96)。

- 元の vault は読むだけ。すべてのノートを type: メモ・visibility: [PIP] で
  個人 vault の 00_PIP/メモ/取り込み_<元の vault 名>/ に元の並びのまま入れる。種類と範囲はあとで「共有する」で選ぶ。
- id は元の属性 created(YYYY-MM-DD HH:mm か YYYY-MM-DD、日本時間)から。時刻がなければ 00:00、
  created がなければファイルの作成日時。2026年より前は 2026-01-01 00:00 から古い順に1秒ずつ詰める。
- 元の属性: created はそのまま残す。この仕組みが使う名前(RESERVED)と入れ子は本文の末尾「## 取り込む前の属性」へ。
- リンクは [[<id>_名前|表示]]、添付は _仕組み/attachments/<id>/(重いものは private_data/<id>/)へコピー。
- id と新しい名前は先に全部決め、書くのは1ノートずつ。書き終えるたびに1秒休む。
- 今あるファイルは書き換えない。取り込み記録.csv にある元のファイルは飛ばすので、何度動かしても同じ結果になる。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

import yaml

from . import frontmatter, ids
from .assign import created_time
from .heavy import file_url, is_heavy, keep_rules
from .lock import Busy, Lock
from .vault import PIP_TOP, SYSTEM_DIR, is_hidden, iter_md

MEMO_DIR = f"{PIP_TOP}/メモ"
RECORD = f"{SYSTEM_DIR}/記録/取り込み記録.csv"
RECORD_HEAD = ["元の vault", "元のパス", "作成", "更新", "元の id", "id", "新しいパス", "中身"]
RESULT_NAME = "00_取り込みの結果.md"
OLD_PROPS = "## 取り込む前の属性"
MAX_PATH = 250  # Windows の上限 260 に少し余裕を残す
PAUSE = 1.0     # 1ノート書くごとに休む秒数

# この仕組みが使う属性の名前(小文字で比べる)。元のノートに同じ名前があれば、属性欄から本文へ移す。
# テンプレートに属性を足したら、ここにも足す(test_importer がテンプレートと突き合わせる)。
RESERVED = {
    "id", "type", "author", "visibility", "project", "parent", "friend", "previous", "generation",
    "価値仮説", "脅かす", "status", "priority", "impact", "speed", "resolution", "due", "kind",
    "value_kind", "parts", "owner", "members", "readers", "attendees", "reviewed_by", "review_request",
    "request_to_manager", "risk_reduction", "usefulness", "secret_refs", "image", "source", "date",
    "week", "drawing_no", "purchaseno", "個数", "単価", "発注先", "lead_weeks", "milestones", "old_ids",
    "excalidraw-plugin", "name", "number",
}
KEEP = {"created"}
ALIASES = {"aliases", "alias"}

CREATED = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?")
WIKI = re.compile(r"(!?)\[\[([^\[\]|#^\n]+)([#^][^\[\]|\n]*)?(\|[^\[\]\n]*)?\]\]")
MDLINK = re.compile(r"(!?)\[([^\[\]\n]*)\]\((<[^>\n]+>|[^)\s]+)\)")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
KEY_LINE = re.compile(r"^([^\s#:-][^:]*?)\s*:(.*)$")


@dataclass
class Item:
    """取り込むノート1つ。"""
    src: Path
    rel: str                 # 元の vault の中のパス(/ 区切り)
    when: datetime | None    # created(なければ None)
    created_raw: str = ""
    new_id: str = ""
    stem: str = ""           # <id>_<名前>
    dest: Path | None = None
    name: str = ""
    done: bool = False       # 前に取り込み済み
    recorded: bool = False   # 取り込み記録.csv に行がある
    digest: str = ""


@dataclass
class Plan:
    src: Path
    personal: Path
    folder: Path
    items: list[Item] = field(default_factory=list)
    others: list[str] = field(default_factory=list)       # どのノートからも使われていないファイル
    no_created: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)   # つながらないリンク
    same_names: list[str] = field(default_factory=list)
    shortened: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)      # 前に取り込んだあと元が変わった
    used_files: set[str] = field(default_factory=set)
    attachments: int = 0


# ---------- 読む ----------

def template_dirs(src: Path) -> set[str]:
    """元の vault の設定にあるテンプレートのフォルダ(コアのテンプレートと Templater)。"""
    out = set()
    for rel, key in ((".obsidian/templates.json", "folder"),
                     (".obsidian/plugins/templater-obsidian/data.json", "templates_folder")):
        try:
            v = json.loads((src / rel).read_text(encoding="utf-8")).get(key)
        except (OSError, ValueError, AttributeError):
            continue
        if v:
            out.add(str(v).strip("/").lower())
    return out


def walk(src: Path) -> tuple[list[str], list[str]]:
    """(ノートのパス, ほかのファイルのパス)。. で始まるフォルダとテンプレートのフォルダは見ない。"""
    skip = template_dirs(src)
    notes, files = [], []
    for dirpath, dirnames, filenames in os.walk(src):
        here = Path(dirpath).relative_to(src).as_posix()
        here = "" if here == "." else here
        dirnames[:] = sorted(d for d in dirnames if not is_hidden(d)
                             and (f"{here}/{d}" if here else d).lower() not in skip)
        for f in sorted(filenames):
            if is_hidden(f):
                continue
            rel = f"{here}/{f}" if here else f
            is_note = f.lower().endswith(".md") and not f.lower().endswith(".excalidraw.md")
            (notes if is_note else files).append(rel)
    return notes, files


def parse_created(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=ids.JST)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=ids.JST)
    m = CREATED.match(str(value or "").strip())
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    try:
        return datetime(y, mo, d, h, mi, s, tzinfo=ids.JST)
    except ValueError:
        return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def fm_blocks(fm: str) -> list[tuple[str, list[str]]]:
    """属性欄をキーごとの行のかたまりに。キーのない行(コメントなど)は前のかたまりにつける。"""
    out: list[tuple[str, list[str]]] = []
    for line in fm.splitlines():
        m = KEY_LINE.match(line)
        if m and not line.startswith((" ", "\t")):
            out.append((m.group(1).strip(), [line]))
        elif out:
            out[-1][1].append(line)
        elif line.strip():
            out.append(("", [line]))
    return out


def is_nested(lines: list[str], value) -> bool:
    if isinstance(value, dict):
        return True
    if isinstance(value, list) and any(isinstance(x, (dict, list)) for x in value):
        return True
    return any(re.match(r"^\s+[^\s#-][^:]*:", ln) for ln in lines[1:])


def yaml_str(s: str) -> str:
    """属性欄の並びに入れる1つの値。そのままだと YAML が読み違える文字があれば引用符で囲む。"""
    if re.fullmatch(r"[^\s\[\]{},:#&*!|>'\"%@`\-?][^\[\]{},#]*?", s) and ": " not in s and not s.endswith(":"):
        try:
            if yaml.safe_load(f"[{s}]") == [s]:
                return s
        except yaml.YAMLError:
            pass
    return json.dumps(s, ensure_ascii=False)


# ---------- 計画 ----------

def load_records(personal: Path) -> dict[tuple[str, str], dict]:
    p = personal / RECORD
    try:
        with p.open(encoding="utf-8-sig", newline="") as f:
            return {(r["元の vault"], r["元のパス"]): r for r in csv.DictReader(f)}
    except (OSError, KeyError, csv.Error):
        return {}


def used_ids(*roots: Path | None) -> set[str]:
    out = set()
    for root in roots:
        if not root or not root.exists():
            continue
        for p, _ in iter_md(root):
            file_id = ids.split_filename(p.stem)[0]
            if file_id:
                out.add(file_id)
    return out


def known_names(*roots: Path | None) -> dict[str, str]:
    """{名前(小文字): ファイル名}。取り込むノートと同じ名前のノートを知らせるため。"""
    out = {}
    for root in roots:
        if not root or not root.exists():
            continue
        for p, rel in iter_md(root):
            if rel.parts[0] == PIP_TOP and len(rel.parts) > 2 and rel.parts[2].startswith("取り込み_"):
                continue
            file_id, name = ids.split_filename(p.stem)
            if file_id:
                out.setdefault(name.lower(), p.stem)
    return out


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "_", name).strip() or "無題"


def make_plan(src: Path, personal: Path, shared: Path | None, code: str) -> Plan:
    src, personal = src.resolve(), personal.resolve()
    folder = personal / MEMO_DIR / f"取り込み_{safe_name(src.name)}"
    plan = Plan(src=src, personal=personal, folder=folder)
    notes, plan.others = walk(src)
    records = load_records(personal)
    used = used_ids(personal, shared)
    for rel in notes:
        p = src / rel
        text = read_text(p)
        fm = frontmatter.load(text)
        raw = next((v for k, v in fm.items() if str(k).lower() == "created"), None)
        item = Item(src=p, rel=rel, when=parse_created(raw), created_raw="" if raw is None else str(raw),
                    name=Path(rel).stem, digest=hashlib.sha1(text.encode("utf-8")).hexdigest())
        if item.when is None:
            plan.no_created.append(rel)
        rec = records.get((src.name, rel))
        if rec:
            item.new_id, item.dest = rec["id"], personal / rec["新しいパス"]
            item.stem = item.dest.stem
            item.done, item.recorded = item.dest.exists(), True
            used.add(item.new_id)
            if item.done and rec.get("中身") and rec["中身"] != item.digest:
                plan.changed.append(rel)
        plan.items.append(item)
    # 元の作成順に並べて id を振る。2026年より前は 2026-01-01 00:00 から詰める
    order = sorted((i for i in plan.items if not i.new_id),
                   key=lambda i: (i.when or created_time(i.src), created_time(i.src), i.rel))
    next_old = 0
    for item in order:
        when = item.when or created_time(item.src)
        sec = ids.seconds_since_epoch(when)
        old = sec < 0
        sec = max(sec, next_old) if old else sec
        while ids.encode_time(sec) + code.upper() in used:
            sec += 1
        item.new_id = ids.encode_time(sec) + code.upper()
        used.add(item.new_id)
        if old:
            next_old = sec + 1
        place(plan, item)
    names = known_names(personal, shared)
    for item in plan.items:
        hit = names.get(item.name.lower())
        if hit:
            plan.same_names.append(f"{item.rel} と [[{hit}]]")
    return plan


def place(plan: Plan, item: Item) -> None:
    """新しいファイル名と場所。パスが長すぎれば名前の部分を短くする(aliases には元の名前をすべて入れる)。"""
    parent = plan.folder / Path(item.rel).parent
    name = safe_name(item.name)
    room = MAX_PATH - len(str(parent)) - len(item.new_id) - 5
    if len(name) > room:
        name = name[:max(room, 8)]
        plan.shortened.append(item.rel)
    item.stem = f"{item.new_id}_{name}"
    item.dest = parent / f"{item.stem}.md"


# ---------- リンクと添付 ----------

class Resolver:
    def __init__(self, plan: Plan):
        self.plan = plan
        self.by_path = {i.rel[:-3].lower(): i for i in plan.items}
        self.by_name: dict[str, list[Item]] = {}
        for i in plan.items:
            self.by_name.setdefault(Path(i.rel).stem.lower(), []).append(i)
        self.files = {f.lower(): f for f in plan.others}
        self.files_by_name: dict[str, list[str]] = {}
        for f in plan.others:
            self.files_by_name.setdefault(Path(f).name.lower(), []).append(f)

    def note(self, target: str, here: str) -> Item | None | str:
        """リンクの行き先のノート。決められないときは "?"、ノートでなければ None。"""
        t = target.strip().replace("\\", "/")
        if t.lower().endswith(".md"):
            t = t[:-3]
        key = t.lower().lstrip("/")
        for cand in (f"{here}/{key}" if here else key, key):
            if cand in self.by_path:
                return self.by_path[cand]
        if "/" in key:
            return None
        found = self.by_name.get(key, [])
        if len(found) > 1:
            same = [i for i in found if str(Path(i.rel).parent.as_posix()).lower() == here.lower()]
            return same[0] if len(same) == 1 else "?"
        return found[0] if found else None

    def file(self, target: str, here: str) -> str | None:
        t = target.strip().replace("\\", "/").lstrip("/")
        for cand in (t, t + ".md"):
            key = cand.lower()
            for k in ((f"{here}/{key}".lower() if here else key), key):
                if k in self.files:
                    return self.files[k]
            found = self.files_by_name.get(Path(cand).name.lower(), [])
            if len(found) == 1 or (found and "/" not in cand):
                return found[0]
        return None


class Writer:
    """1ノート分の添付のコピーを覚える(書くのは write のとき)。"""

    def __init__(self, plan: Plan, item: Item, private_data: Path | None, rules: dict):
        self.plan, self.item = plan, item
        self.private_data, self.rules = private_data, rules
        self.copies: list[tuple[Path, Path]] = []
        self.names: dict[str, str] = {}   # 元のパス → 置いた名前
        self.heavy_left = False

    def attach(self, rel: str) -> tuple[str, bool]:
        """(リンクに書く行き先, 重い添付か)。"""
        src = self.plan.src / rel
        heavy = is_heavy(src, self.rules)
        if heavy and self.private_data:
            base = self.private_data / self.item.new_id
        else:
            base = self.plan.personal / SYSTEM_DIR / "attachments" / self.item.new_id
            self.heavy_left |= heavy
        if rel not in self.names:
            name, n = src.name, 2
            taken = set(self.names.values())
            while name in taken:
                stem, dot, ext = src.name.rpartition(".")
                name = f"{stem}_{n}.{ext}" if dot else f"{src.name}_{n}"
                n += 1
            self.names[rel] = name
            self.copies.append((src, base / name))
            self.plan.used_files.add(rel)
        dest = base / self.names[rel]
        if heavy and self.private_data:
            return file_url(dest), True
        return dest.relative_to(self.plan.personal).as_posix(), False


def rewrite(text: str, item: Item, res: Resolver, w: Writer, plan: Plan) -> str:
    here = Path(item.rel).parent.as_posix()
    here = "" if here == "." else here

    def note_link(target: Item, shown: str, sub: str = "") -> str:
        return f"[[{target.stem}{sub}|{shown}]]"

    def wiki(m: re.Match) -> str:
        bang, target, sub, alias = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        hit = res.note(target, here)
        if hit == "?":
            plan.unresolved.append(f"{item.rel}: [[{target}]](同じ名前が2つ以上)")
            return m.group(0)
        if isinstance(hit, Item):
            shown = alias[1:] if alias else Path(target.replace("\\", "/")).name.removesuffix(".md")
            return note_link(hit, shown, sub)
        f = res.file(target, here)
        if f:
            dest, heavy = w.attach(f)
            shown = alias[1:] if alias else Path(f).name
            if heavy:
                return f"[{shown}]({dest})"
            return f"{bang}[[{dest}{'|' + alias[1:] if alias else ''}]]"
        plan.unresolved.append(f"{item.rel}: [[{target}]]")
        return m.group(0)

    def md(m: re.Match) -> str:
        bang, shown, dest = m.group(1), m.group(2), m.group(3)
        inner = unquote(dest[1:-1] if dest.startswith("<") else dest)
        if SCHEME.match(inner) or inner.startswith("#"):
            return m.group(0)
        path, _, sub = inner.partition("#")
        hit = res.note(path, here)
        if isinstance(hit, Item):
            return note_link(hit, shown or hit.name, f"#{sub}" if sub else "")
        f = res.file(path, here)
        if f:
            target, heavy = w.attach(f)
            if heavy:
                return f"[{shown or Path(f).name}]({target})"
            return f"{bang}[[{target}{'|' + shown if shown and not bang else ''}]]"
        plan.unresolved.append(f"{item.rel}: ({inner})")
        return m.group(0)

    # ノートの埋め込み ![[ノート]] は note_link がふつうのリンクにする
    return MDLINK.sub(md, WIKI.sub(wiki, text))


# ---------- 1ノートを組み立てる ----------

def build(item: Item, res: Resolver, w: Writer, plan: Plan, me: str) -> str:
    text = read_text(item.src)
    fm_text, body = frontmatter.split(text)
    data = frontmatter.load(text) if fm_text else {}
    kept, moved, aliases = [], [], [item.name]
    broken = fm_text is not None and fm_text.strip() and not data
    for key, lines in ([] if broken else fm_blocks(fm_text or "")):
        low = key.lower()
        value = data.get(key)
        if low in ALIASES:
            aliases += [a for a in frontmatter.as_list(value) if a not in aliases]
        elif low in KEEP or (low and low not in RESERVED and not is_nested(lines, value)):
            kept += lines
        elif low in RESERVED and not is_nested(lines, value):
            shown = ", ".join(frontmatter.as_list(value)) if isinstance(value, list) else lines[0].split(":", 1)[1].strip()
            moved.append(f"- {key}: {shown}")
        else:
            moved.append("\n```yaml\n" + "\n".join(lines) + "\n```\n")
    if broken:
        moved.append("\n```yaml\n" + fm_text + "\n```\n")
    head = [f"id: {item.new_id}", "type: メモ", f"author: [{yaml_str(me)}]",
            f"aliases: [{', '.join(yaml_str(a) for a in aliases)}]", "visibility: [PIP]", *kept]
    body = body.lstrip("\r\n")
    if moved:
        body = body.rstrip() + f"\n\n{OLD_PROPS}\n\n" + "\n".join(moved).strip("\n") + "\n"
    return rewrite("---\n" + "\n".join(head) + "\n---\n" + body, item, res, w, plan)


# ---------- 書く ----------

def append_record(plan: Plan, item: Item, old_id: str) -> None:
    p = plan.personal / RECORD
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    st = item.src.stat()
    with p.open("a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        out = csv.writer(f)
        if new:
            out.writerow(RECORD_HEAD)
        out.writerow([plan.src.name, item.rel, item.created_raw or created_time(item.src).strftime("%Y-%m-%d %H:%M"),
                      datetime.fromtimestamp(st.st_mtime, tz=ids.JST).strftime("%Y-%m-%d %H:%M"), old_id,
                      item.new_id, item.dest.relative_to(plan.personal).as_posix(), item.digest])


def run(plan: Plan, me: str, private_data: Path | None, shared: Path | None, dry: bool,
        pause: float = PAUSE, say=print) -> list[Item]:
    """取り込む。dry なら書かずに数えるだけ。戻り値は書いたノート。"""
    res = Resolver(plan)
    rules = keep_rules(shared)
    todo = [i for i in plan.items if not i.done]
    written, heavy_left = [], 0
    for n, item in enumerate(todo, 1):
        w = Writer(plan, item, private_data, rules)
        text = build(item, res, w, plan, me)
        plan.attachments += len(w.copies)
        heavy_left += w.heavy_left
        if dry:
            continue
        if item.dest.exists():
            say(f"飛ばしました(同じ名前のファイルがあります): {item.dest}")
            continue
        old_id = next((str(v) for k, v in frontmatter.load(read_text(item.src)).items() if str(k).lower() == "id"), "")
        if not item.recorded:
            append_record(plan, item, old_id)
        for src, dest in w.copies:
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        item.dest.parent.mkdir(parents=True, exist_ok=True)
        with item.dest.open("w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        st = item.src.stat()
        os.utime(item.dest, (st.st_atime, st.st_mtime))  # 更新日時は元のまま
        written.append(item)
        say(f"{len(todo)} 件中 {n} 件目: {item.rel}")
        if pause and n < len(todo):
            time.sleep(pause)
    if heavy_left:
        plan.unresolved.append(f"重い添付のあるノートが {heavy_left} つあります。private_data が設定にないので vault に入れました(次の同期で移します)")
    return written


def result_text(plan: Plan, written: int, dry: bool) -> str:
    def part(title: str, rows: list[str]) -> list[str]:
        return [f"## {title}({len(rows)})", "", *[f"- {r}" for r in rows], ""] if rows else []

    unused = [f for f in plan.others if f not in plan.used_files]
    lines = [f"# 取り込みの結果({plan.src.name})", "",
             f"- {datetime.now(ids.JST):%Y-%m-%d %H:%M} {'試し実行' if dry else '取り込み'}",
             f"- ノート {len(plan.items)} 件(今回 {written} 件、前に取り込み済み {sum(i.done for i in plan.items)} 件)、添付 {plan.attachments} 件",
             "- 共有したいノートは、ノートの上の帯のボタンか右クリックの「共有する」で種類とだれに見せるかを選ぶ。", ""]
    lines += part("つながらないリンク", sorted(set(plan.unresolved)))
    lines += part("同じ名前のノート(まとめていません)", plan.same_names)
    lines += part("created のないノート(ファイルの作成日時で id をつけた)", plan.no_created)
    lines += part("パスが長いので名前を短くしたノート", plan.shortened)
    lines += part("前に取り込んだあと元が変わったノート(上書きしていません)", plan.changed)
    lines += part("取り込まなかったファイル(どのノートからも使われていない)", unused)
    return "\n".join(lines)


def import_vault(src: Path, personal: Path, shared: Path | None, private_data: Path | None,
                 code: str, me: str, lock_path: Path, dry: bool, pause: float = PAUSE,
                 wait: float = 15 * 60, say=print) -> Path:
    """取り込む(dry なら試し実行)。結果のファイルのパスを返す。"""
    src = src.resolve()
    if not src.is_dir():
        raise ValueError(f"フォルダが見つかりません: {src}")
    if src == personal.resolve() or personal.resolve() in src.parents or src in personal.resolve().parents:
        raise ValueError("個人 vault そのもの(かその中)は取り込めません")
    plan = make_plan(src, personal, shared, code)
    if dry:
        run(plan, me, private_data, shared, dry=True)
        text = result_text(plan, 0, True)
        say(text)
        return plan.folder / RESULT_NAME
    deadline = time.time() + wait
    while True:
        try:
            lock = Lock(lock_path).acquire()
            break
        except Busy as e:
            if time.time() > deadline:
                raise ValueError(f"別の PC({e.pc})が同期しています。あとでもう一度押してください")
            say(f"別の PC({e.pc})の同期が終わるのを待っています…")
            time.sleep(10)
    try:
        written = run(plan, me, private_data, shared, dry=False, pause=pause, say=say)
        plan.folder.mkdir(parents=True, exist_ok=True)
        out = plan.folder / RESULT_NAME
        out.write_text(result_text(plan, len(written), False), encoding="utf-8")
        return out
    finally:
        lock.release()
