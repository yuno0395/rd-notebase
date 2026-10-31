"""人の書き方「番号_名前」(仕様書 v0.68)。author・reviewed_by・members を番号で見分け、名前だけの古い書き方も読む。"""

from pathlib import Path

import pytest

from notesync import frontmatter
from notesync.config import Config, member_code, member_number
from notesync.run import run_once
from notesync.vault import has_person, is_theirs, person, person_labels, person_name, same_person

from .conftest import text

PJ = "試しPJ"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(body)
    return path


def test_person_forms():
    assert person("229999_Yu") == ("229999", "Yu")
    assert person("Yu") == ("", "Yu")
    assert person("[[229999_Yu]]") == ("229999", "Yu")
    assert person_name("229999_Yu") == "Yu"
    # 番号が両方にあれば番号で、片方が名前だけなら名前で比べる
    assert same_person("229999_Yu", "229999_Yu")
    assert not same_person("123456_Yu", "229999_Yu")      # 同姓同名は別の人
    assert same_person("Yu", "229999_Yu")                  # 古い書き方も同じ人
    assert not same_person("佐藤", "229999_Yu")
    assert has_person(["佐藤", "229999_Yu"], "Yu")
    assert is_theirs({"author": "123456_Yu"}, "229999_Yu")
    assert not is_theirs({"author": ["佐藤", "229999_Yu"]}, "229999_Yu")
    assert not is_theirs({"author": "Yu"}, "229999_Yu")
    assert not is_theirs({}, "229999_Yu")


def test_labels_show_number_only_for_same_names():
    got = person_labels(["229999_Yu", "123456_Yu", "Yu", "345678_佐藤", "佐藤"])
    assert got["229999_Yu"] == "Yu(229999)" and got["123456_Yu"] == "Yu(123456)"
    assert got["345678_佐藤"] == "佐藤" and got["佐藤"] == "佐藤"


@pytest.fixture
def cloud(tmp_path):
    root = tmp_path / "Box"
    shared = root / "共有"
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv",
          "名前,番号,使い始めた日\nYu,229999,2026-10-24\n佐藤,345678,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md",
          "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [229999_Yu, 佐藤]\n---\n")
    yu = root / "個人_Yu"
    write(yu / "_仕組み/個人設定.md", "---\nname: Yu\nnumber: 229999\n---\n")
    write(yu / "共通/02_ノード/0RB0014XGV_水.md", "---\nid: 0RB0014XGV\ntype: ノード\n---\n水の話\n")
    write(yu / "共通/02_ノード/0RB0024XGV_油.md", "---\nid: 0RB0024XGV\ntype: ノード\nauthor: Yu\n---\n古い書き方\n")
    sato = root / "個人_佐藤"
    write(sato / "_仕組み/個人設定.md", "---\nname: 佐藤\n---\n")   # number がなくても メンバー.csv で読む

    def cfg(member):
        c = Config(member=member, personal=root / f"個人_{member}", shared=shared,
                   backup_dir=tmp_path / f"backup_{member}", state_dir=tmp_path / f"state_{member}",
                   idle_seconds=0)
        c.code = member_code(c)
        c.number = member_number(c)
        return c

    return {"shared": shared, "yu": cfg("Yu"), "sato": cfg("佐藤")}


def test_me_is_number_and_name(cloud):
    assert cloud["yu"].me == "229999_Yu"
    assert cloud["sato"].me == "345678_佐藤"


def test_sync_writes_number_and_reads_old_names(cloud):
    run_once(cloud["yu"])
    note = cloud["yu"].personal / "共通/02_ノード/0RB0014XGV_水.md"
    assert frontmatter.load(text(note))["author"] == "229999_Yu"
    old = cloud["shared"] / "共通/02_ノード/0RB0024XGV_油.md"
    assert old.exists()                                             # 名前だけの author も自分のノートとして出す
    assert frontmatter.load(text(old))["author"] == "Yu"            # 書き換えない
    # 佐藤には配る(members の 佐藤 は名前だけ)。Yu には配り直さない(F-10)
    run_once(cloud["sato"])
    assert (cloud["sato"].personal / "共通/02_ノード/0RB0014XGV_水.md").exists()
    run_once(cloud["yu"])
    assert sorted(p.name for p in (cloud["yu"].personal / "共通/02_ノード").glob("*.md")) == \
        ["0RB0014XGV_水.md", "0RB0024XGV_油.md"]
    assert "他の人のノート" not in text(cloud["yu"].personal / "_仕組み/同期レポート.md")


def test_same_name_other_number_is_theirs(cloud):
    """同じ名前でも番号が違えば他の人のノート(手元で書き換えても共有の中身に戻す)。"""
    shared_note = write(cloud["shared"] / "共通/02_ノード/0RB0030001_鉄.md",
                        "---\nid: 0RB0030001\ntype: ノード\nauthor: 123456_Yu\n---\n鉄の話\n")
    run_once(cloud["yu"])
    copy = cloud["yu"].personal / "共通/02_ノード/0RB0030001_鉄.md"
    assert copy.exists()
    write(copy, text(copy) + "書いてしまった\n")
    run_once(cloud["yu"])
    assert "書いてしまった" not in text(copy)
    assert "書いてしまった" not in text(shared_note)
