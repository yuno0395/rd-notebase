"""F-17b: id のないノートに貼った添付を _仕組み/attachments/<id>/ へ移し、リンクの形をそろえる。"""

from datetime import datetime

from notesync import ids
from notesync.config import Config, member_code
from notesync.run import run_once

from .test_heavy import write

NOW = datetime(2026, 10, 24, 9, 0, tzinfo=ids.JST).timestamp()


def setup(tmp_path):
    personal = tmp_path / "個人"
    write(personal / "_仕組み/記録/私.yaml", 'name: Yu\ncode: "001"\n')
    c = Config(member="Yu", personal=personal, shared=None, backup_dir=tmp_path / "b",
               state_dir=tmp_path / "s", idle_seconds=0)
    c.code = member_code(c)
    return c, personal


def only_md(root, top):
    return [p for p in (root / top).glob("*.md")]


def test_loose_attachment_moves_with_new_id(tmp_path):
    c, v = setup(tmp_path)
    write(v / "_仕組み/attachments/成形品.jpg", b"jpg")
    write(v / "_仕組み/attachments/Pasted image 1.png", b"png")
    write(v / "05_ナレッジ/ヒケの原因.md",
          "# ヒケの原因\n![[成形品.jpg]]\n![図](<_仕組み/attachments/Pasted image 1.png>)\n")
    run_once(c, dry_run=False, now=NOW)
    note = only_md(v, "05_ナレッジ")[0]
    nid = ids.split_filename(note.stem)[0]
    assert nid
    att = v / "_仕組み/attachments" / nid
    assert (att / "成形品.jpg").read_bytes() == b"jpg"
    assert (att / "Pasted image 1.png").exists()
    assert not (v / "_仕組み/attachments/成形品.jpg").exists()
    body = note.read_text(encoding="utf-8")
    assert f"![[_仕組み/attachments/{nid}/成形品.jpg]]" in body
    assert f"![図](<_仕組み/attachments/{nid}/Pasted image 1.png>)" in body


def test_dry_run_changes_nothing(tmp_path):
    c, v = setup(tmp_path)
    write(v / "_仕組み/attachments/成形品.jpg", b"jpg")
    write(v / "05_ナレッジ/ヒケの原因.md", "![[成形品.jpg]]\n")
    rep = run_once(c, dry_run=True, now=NOW)
    assert (v / "_仕組み/attachments/成形品.jpg").exists()
    assert (v / "05_ナレッジ/ヒケの原因.md").read_text(encoding="utf-8") == "![[成形品.jpg]]\n"
    assert any("添付を移した" in r for r in rep.records)


def test_shared_loose_attachment_stays(tmp_path):
    c, v = setup(tmp_path)
    write(v / "_仕組み/attachments/成形品.jpg", b"jpg")
    write(v / "05_ナレッジ/ヒケ.md", "![[成形品.jpg]]\n")
    write(v / "00_日誌/デイリー/2026-10-24.md", "![[成形品.jpg]]\n")
    rep = run_once(c, dry_run=False, now=NOW)
    assert (v / "_仕組み/attachments/成形品.jpg").exists()
    assert any("2 つのノートが指している" in t for t in rep.todos)


def test_short_link_to_own_folder_becomes_full_path(tmp_path):
    c, v = setup(tmp_path)
    nid = "0RB001001"
    write(v / f"_仕組み/attachments/{nid}/図面.pdf", b"pdf")
    write(v / f"03_イシュー/{nid}_ヒケ.md", f"---\nid: {nid}\nauthor: Yu\n---\n[図面](図面.pdf)\n![[図面.pdf]]\n")
    run_once(c, dry_run=False, now=NOW)
    body = (v / f"03_イシュー/{nid}_ヒケ.md").read_text(encoding="utf-8")
    assert f"[図面](_仕組み/attachments/{nid}/図面.pdf)" in body
    assert f"![[_仕組み/attachments/{nid}/図面.pdf]]" in body


def test_diary_attachment_moves_to_date_folder(tmp_path):
    """日誌には id がないので、ファイル名(日付)のフォルダ 日誌/<日付>/ へ移す。"""
    c, v = setup(tmp_path)
    write(v / "_仕組み/attachments/成形品.jpg", b"jpg")
    write(v / "_仕組み/attachments/まとめ.pdf", b"pdf")
    write(v / "00_日誌/デイリー/2026-10-24.md", "# 2026-10-24\n![[成形品.jpg]]\n")
    write(v / "00_日誌/週報/2026-W43.md", "![資料](_仕組み/attachments/まとめ.pdf)\n")
    run_once(c, dry_run=False, now=NOW)
    day = v / "_仕組み/attachments/日誌/2026-10-24"
    assert (day / "成形品.jpg").read_bytes() == b"jpg"
    assert (v / "_仕組み/attachments/日誌/2026-W43/まとめ.pdf").exists()
    assert not (v / "_仕組み/attachments/成形品.jpg").exists()
    # 日誌のファイル名は変えない(id をつけない)
    daily = v / "00_日誌/デイリー/2026-10-24.md"
    assert "![[_仕組み/attachments/日誌/2026-10-24/成形品.jpg]]" in daily.read_text(encoding="utf-8")
    weekly = v / "00_日誌/週報/2026-W43.md"
    assert "![資料](_仕組み/attachments/日誌/2026-W43/まとめ.pdf)" in weekly.read_text(encoding="utf-8")


def test_inbox_attachment_stays(tmp_path):
    c, v = setup(tmp_path)
    write(v / "_仕組み/attachments/成形品.jpg", b"jpg")
    write(v / "00_inbox/メモ.md", "![[成形品.jpg]]\n")
    run_once(c, dry_run=False, now=NOW)
    assert (v / "_仕組み/attachments/成形品.jpg").exists()
