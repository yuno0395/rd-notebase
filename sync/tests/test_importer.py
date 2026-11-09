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


# 圧縮した図の中身(lz-string 1.5.0 の compressToBase64 で作ったもの)。
# {"type":"excalidraw","elements":[{"id":"a","type":"text","text":"[[水]] と [[写真.png]]","rawText":"[[水]]",
#   "originalText":"[[水]]","link":"[[水]]"},{"id":"b","type":"rectangle","link":"[[b]]"}]}
COMPRESSED = ("N4IgLgngDgpiBcIYA8DGBDANgSwCYCd0B3EAGiUxgFsYA7MAZwQG1Q8ER0zxo5EwUYbgORDEzZoBYbALrSABIAsGORMCZioHx3AHRRaAc1ndCRACqCOEmdO4B7fNh3ZaWE6LNT95HLQDWriyAC+pGy4HABGwrwc+DCoYOi6lNyePuLMofr+0v5AA")


def drawing(kind: str, data: str, links: str) -> str:
    return (f"---\nexcalidraw-plugin: parsed\n---\n# Excalidraw Data\n\n## Text Elements\n{links} ^a\n\n"
            f"## Embedded Files\nabc123: [[写真.png]]\n\n%%\n## Drawing\n```{kind}\n{data}\n```\n%%\n")


def test_lz_decompress():
    raw = importer.lz_decompress_b64(COMPRESSED)
    assert '"rawText":"[[水]]"' in raw and '"link":"[[b]]"' in raw


@pytest.mark.parametrize("kind", ["json", "compressed-json"])
def test_links_in_drawing(env, kind):
    """図(Excalidraw)の中のリンクも直す。"""
    src, personal, _ = env
    put(src / "水.md", "---\ncreated: 2026-04-01\n---\n水\n")
    put(src / "写真.png", b"\x89PNG")
    data = COMPRESSED if kind == "compressed-json" else (
        '{"type":"excalidraw","elements":[{"id":"a","type":"text","text":"[[水]] と [[写真.png]]",'
        '"rawText":"[[水]]","originalText":"[[水]]","link":"[[水]]"},{"id":"b","type":"rectangle","link":"[[b]]"}]}')
    put(src / "図/絵.excalidraw.md", drawing(kind, data, "[[水]]"))
    put(src / "e.md", "---\ncreated: 2026-04-02\n---\n![[絵.excalidraw]]\n")
    go(env)
    got = imported(personal)
    e_id = ids.split_filename(got["e"].stem)[0]
    w, b = got["水"].stem, got["b"].stem
    assert f"![[_仕組み/attachments/{e_id}/絵.excalidraw.md]]" in got["e"].read_text(encoding="utf-8")
    pic = (personal / "_仕組み/attachments" / e_id / "絵.excalidraw.md").read_text(encoding="utf-8")
    assert f"[[{w}|水]] ^a" in pic                                        # 文字の欄
    assert f"abc123: [[_仕組み/attachments/{e_id}/写真.png]]" in pic        # 貼った画像
    assert (personal / "_仕組み/attachments" / e_id / "写真.png").exists()
    body = re.search(r"```json\n(.*?)\n```", pic, re.S)
    assert body, "図の中身は json で書く"
    doc = __import__("json").loads(body.group(1))
    a, r = doc["elements"]
    assert a["link"] == f"[[{w}|水]]" and a["rawText"] == f"[[{w}|水]]"
    assert a["text"] == f"[[{w}|水]] と [[_仕組み/attachments/{e_id}/写真.png]]"
    assert r["link"] == f"[[{b}|b]]"


def test_repair_old_drawing(env):
    """前の版で取り込んだ図(元のままの写し)は、もう一度押すと中のリンクが直る。手を入れた図は触らない。"""
    src, personal, _ = env
    put(src / "水.md", "---\ncreated: 2026-04-01\n---\n水\n")
    put(src / "絵.excalidraw.md", drawing("json", '{"type":"excalidraw","elements":[]}', "[[水]]"))
    put(src / "e.md", "---\ncreated: 2026-04-02\n---\n![[絵.excalidraw]]\n")
    go(env)
    got = imported(personal)
    e_id = ids.split_filename(got["e"].stem)[0]
    pic = personal / "_仕組み/attachments" / e_id / "絵.excalidraw.md"
    pic.write_bytes((src / "絵.excalidraw.md").read_bytes())   # 前の版はそのままコピーしていた
    go(env)
    assert f"[[{got['水'].stem}|水]] ^a" in pic.read_text(encoding="utf-8")
    pic.write_text("手で直した図", encoding="utf-8")
    go(env)
    assert pic.read_text(encoding="utf-8") == "手で直した図"
