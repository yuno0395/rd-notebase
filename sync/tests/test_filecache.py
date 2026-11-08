import os
from pathlib import Path

from notesync import filecache
from notesync.state import digest
from notesync.vault import read, write


def test_walk_md_matches_rglob_and_skips(tmp_path: Path):
    for rel in ["a.md", "共通/02_ノード/b.md", "共通/02_ノード/c.txt", ".obsidian/x.md",
                "共通/.trash/y.md", "_仕組み/templates/t.md", "_仕組み/attachments/ID/z.md", "deep/1/2/3/d.md"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    everything = [p for p in sorted(tmp_path.rglob("*.md"))
                  if not any(x.startswith(".") for x in p.relative_to(tmp_path).parts)]
    assert filecache.walk_md(tmp_path) == everything
    got = filecache.walk_md(tmp_path, {"_仕組み"})
    assert got == [p for p in everything if p.relative_to(tmp_path).parts[0] != "_仕組み"]
    # 一番上だけを外す(深いところの同じ名前は外さない)
    (tmp_path / "共通/_仕組み").mkdir()
    (tmp_path / "共通/_仕組み/e.md").write_text("x", encoding="utf-8")
    assert tmp_path / "共通/_仕組み/e.md" in filecache.walk_md(tmp_path, {"_仕組み"})


def test_read_notices_changes(tmp_path: Path):
    p = tmp_path / "n.md"
    p.write_text("一", encoding="utf-8")
    assert read(p) == "一"
    p.write_text("二二", encoding="utf-8")  # ほかのアプリが書き換えた(大きさが変わる)
    assert read(p) == "二二"
    st = os.stat(p)
    p.write_text("三三", encoding="utf-8")  # 同じ大きさでも、時刻が変われば読み直す
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert read(p) == "三三"
    write(p, "四四")  # 自分で書いたら、時刻を戻されても読み直す
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert read(p) == "四四"


def test_digest_notices_changes(tmp_path: Path):
    p = tmp_path / "a.png"
    p.write_bytes(b"1")
    h1 = digest(p)
    p.write_bytes(b"22")
    assert digest(p) != h1


def test_walk_files_and_only_tops(tmp_path: Path):
    for rel in ["a.md", "00_inbox/b.md", "00_inbox/x/c.md", "共通/d.md", ".obsidian/e.json",
                "_仕組み/attachments/ID/.f", "_仕組み/attachments/ID/.h/g.png", "_仕組み/attachments/ID/i.png"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    files = [p for p in sorted(tmp_path.rglob("*")) if p.is_file()]
    # 隠しフォルダの中は見ない(隠しファイルは見る)
    assert filecache.walk_files(tmp_path) == [
        p for p in files if not any(x.startswith(".") for x in p.relative_to(tmp_path).parts[:-1])]
    assert filecache.walk_files(tmp_path / "_仕組み/attachments/ID", hidden=True) == [
        p for p in files if "attachments" in p.parts]
    # 一番上は 00_inbox だけ
    assert filecache.walk_md(tmp_path, only_tops=("00_inbox",)) == [tmp_path / "00_inbox/b.md",
                                                                   tmp_path / "00_inbox/x/c.md"]
    assert filecache.walk_files(tmp_path / "ない") == []
