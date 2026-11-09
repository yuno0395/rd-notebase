"""F-62: 別の Obsidian の vault からの取り込み(仕様書「別の Obsidian から取り込む」)。"""

import hashlib
import re
from pathlib import Path

import pytest

from notesync import frontmatter, ids, importer

ROOT = Path(__file__).resolve().parents[2]
CODE = "4XGV"
ME = "229999_yu"


def put(p: Path, text: str | bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.write_bytes if isinstance(text, bytes) else lambda t: p.write_text(t, encoding="utf-8"))(text)
    return p


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def env(tmp_path):
    src = tmp_path / "旧ノート"
    personal = tmp_path / "個人"
    private = tmp_path / "自分用"
    put(personal / "_仕組み/個人設定.md", "---\nname: yu\n---\n")
    put(src / ".obsidian/templates.json", '{"folder": "Templates"}')
    put(src / "Templates/ひな形.md", "---\ncreated: \n---\n")
    put(src / "a.md", "---\nid: 20240501-xyz\ncreated: 2024-05-01 09:30\ntags: [設計]\nstatus: done\n"
        "aliases: [エー]\nmeta:\n  owner: x\n---\n本文 [[b]] [[b|びー]] [[sub/c]] [[b#見出し]] ![[b]]\n"
        "[md](b.md) ![[img.png]] ![](img.png) [[nope]] https://example.com [xl](data.xlsx)\n")
    put(src / "b.md", "---\ncreated: 2026-03-01\n---\nB\n")
    put(src / "sub/c.md", "---\ncreated: 2023-01-01 00:00\n---\nC\n")
    put(src / "d.md", "本文だけ\n")
    put(src / "img.png", b"\x89PNG")
    put(src / "data.xlsx", b"xlsx")
    put(src / "unused.pdf", b"%PDF")
    return src, personal, private


def go(env, dry=False, pause=0):
    src, personal, private = env
    return importer.import_vault(src, personal, None, private, CODE, ME, personal / "_仕組み/記録/同期中.lock",
                                 dry=dry, pause=pause, say=lambda *_: None)


def imported(personal: Path) -> dict[str, Path]:
    folder = personal / importer.MEMO_DIR / "取り込み_旧ノート"
    return {ids.split_filename(p.stem)[1]: p for p in folder.rglob("*.md") if p.name != importer.RESULT_NAME}


def test_ids_from_created(env):
    go(env)
    got = imported(env[1])
    assert set(got) == {"a", "b", "c", "d"}
    when = {k: ids.decode_time(ids.split_filename(p.stem)[0]) for k, p in got.items()}
    # 2026年より前は 2026-01-01 00:00 から古い順に詰める(c は 2023 年、a は 2024 年)
    assert when["c"] == ids.EPOCH
    assert (when["a"] - ids.EPOCH).total_seconds() == 1
    # 時刻のない created はその日の 00:00
    assert when["b"].strftime("%Y-%m-%d %H:%M") == "2026-03-01 00:00"
    assert all(ids.split_filename(p.stem)[0].endswith(CODE) for p in got.values())
    # 元の並びのまま
    assert got["c"].parent.name == "sub"


def test_frontmatter(env):
    go(env)
    text = imported(env[1])["a"].read_text(encoding="utf-8")
    fm = frontmatter.load(text)
    new_id = ids.split_filename(imported(env[1])["a"].stem)[0]
    assert fm["id"] == new_id and fm["type"] == "メモ" and fm["visibility"] == ["PIP"]
    assert fm["author"] == [ME] and fm["aliases"] == ["a", "エー"]
    assert "created: 2024-05-01 09:30" in text      # 本当の日時はそのまま
    assert fm["tags"] == ["設計"]                    # この仕組みが使わない属性は残す
    assert "status" not in fm and "meta" not in fm  # 同じ名前と入れ子は本文へ
    body = frontmatter.split(text)[1]
    assert "## 取り込む前の属性" in body
    assert "- id: 20240501-xyz" in body and "- status: done" in body and "  owner: x" in body
    d = frontmatter.load(imported(env[1])["d"].read_text(encoding="utf-8"))
    assert d["aliases"] == ["d"]


def test_links_and_attachments(env):
    src, personal, private = env
    go(env)
    got = imported(personal)
    stem = {k: p.stem for k, p in got.items()}
    a_id = ids.split_filename(stem["a"])[0]
    body = frontmatter.split(got["a"].read_text(encoding="utf-8"))[1]
    assert f"[[{stem['b']}|b]]" in body and f"[[{stem['b']}|びー]]" in body
    assert f"[[{stem['c']}|c]]" in body and f"[[{stem['b']}#見出し|b]]" in body
    assert f"![[{stem['b']}" not in body              # ノートの埋め込みはふつうのリンクに
    assert f"[[{stem['b']}|md]]" in body
    assert body.count(f"![[_仕組み/attachments/{a_id}/img.png]]") == 2
    assert "[[nope]]" in body and "https://example.com" in body
    assert (personal / "_仕組み/attachments" / a_id / "img.png").read_bytes() == b"\x89PNG"
    # 重い添付は自分用の置き場へ
    assert (private / a_id / "data.xlsx").exists()
    assert re.search(r"\[xl\]\(file:///.*data\.xlsx\)", body)
    # 使われていないファイルはコピーせず結果に出す
    result = (got["a"].parents[0] / importer.RESULT_NAME).read_text(encoding="utf-8")
    assert "unused.pdf" in result and "[[nope]]" in result
    assert not list(personal.rglob("unused.pdf"))
    assert not list(personal.rglob("ひな形*"))     # テンプレートのフォルダは取り込まない
    rec = (personal / importer.RECORD).read_text(encoding="utf-8-sig")
    assert "20240501-xyz" in rec and "a.md" in rec


def test_source_untouched_and_rerun_same(env):
    src, personal, _ = env
    before = snapshot(src)
    go(env)
    first = snapshot(personal)
    go(env)
    assert snapshot(src) == before
    after = snapshot(personal)
    after.pop(f"{importer.MEMO_DIR}/取り込み_旧ノート/{importer.RESULT_NAME}")
    first.pop(f"{importer.MEMO_DIR}/取り込み_旧ノート/{importer.RESULT_NAME}")
    assert after == first


def test_dry_run_writes_nothing(env):
    personal = env[1]
    before = snapshot(personal)
    go(env, dry=True)
    assert snapshot(personal) == before


def test_pause_between_notes(env, monkeypatch):
    slept = []
    monkeypatch.setattr(importer.time, "sleep", lambda s: slept.append(s))
    go(env, pause=1.0)
    assert slept == [1.0] * 3   # 4ノート、書き終えるたびに休む(最後のあとは休まない)


def test_skip_used_id(env):
    src, personal, _ = env
    taken = ids.encode_time(0) + CODE
    put(personal / f"共通/02_ノード/{taken}_既存.md", f"---\nid: {taken}\n---\n")
    go(env)
    c = imported(personal)["c"]
    assert not c.stem.startswith(taken)


def test_reserved_covers_templates():
    """テンプレートの属性名は、すべて RESERVED に入っている(属性を足したときの直し忘れで、元の属性とぶつからないように)。"""
    names = set()
    for p in list((ROOT / "vault").glob("*/_仕組み/templates/*.md")):
        fm, _ = frontmatter.split(p.read_text(encoding="utf-8"))
        for line in (fm or "").splitlines():
            m = re.match(r"^([^\s#:-][^:]*?)\s*:", line)
            if m:
                names.add(m.group(1).strip().lower())
    missing = names - importer.RESERVED - importer.KEEP - importer.ALIASES
    assert not missing, f"importer.RESERVED に足してください: {sorted(missing)}"
