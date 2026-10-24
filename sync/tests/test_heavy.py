"""F-17〜20: 重い添付を 開発データ/ へ移し、リンクを書き換える。"""

from datetime import datetime
from pathlib import Path

import pytest

from notesync import ids
from notesync.config import Config, member_code
from notesync.heavy import file_url, relink, to_personal, to_shared
from notesync.run import run_once

from .conftest import text

PJ = "試しPJ"
NOW = datetime(2026, 10, 24, 9, 0, tzinfo=ids.JST).timestamp()


def write(path: Path, body, mode="w") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        path.write_bytes(body)
    else:
        with path.open(mode, encoding="utf-8", newline="") as f:
            f.write(body)
    return path


@pytest.fixture
def box(tmp_path):
    root = tmp_path / "Box"
    shared = root / "共有"
    data = root / "開発データ"
    data.mkdir(parents=True)
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv",
          "名前,記号,使い始めた日\nYu,001,2026-10-24\n佐藤,002,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md", "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [Yu, 佐藤]\n---\n")

    def cfg(member, code, data_dir):
        personal = root / f"個人_{member}"
        write(personal / "_仕組み/記録/私.yaml", f'name: {member}\ncode: "{code}"\n')
        c = Config(member=member, personal=personal, shared=shared, shared_data=data_dir,
                   backup_dir=tmp_path / f"backup_{member}", state_dir=tmp_path / f"state_{member}",
                   idle_seconds=0)
        c.code = member_code(c)
        return c

    # 佐藤の PC では Box の場所が違う(同じ 開発データ を別のパスで見ている)
    sato_view = tmp_path / "佐藤のPC" / "開発データ"
    sato_view.parent.mkdir(parents=True)
    try:
        sato_view.symlink_to(data, target_is_directory=True)
    except OSError:  # Windows で権限がないときは、同じ場所で確かめる
        sato_view = data
    return {"data": data, "shared": shared, "yu": cfg("Yu", "001", data), "sato": cfg("佐藤", "002", sato_view)}


def issue(c, nid="0RB001001", project=PJ, body="") -> Path:
    return write(c.personal / f"03_イシュー/{nid}_ヒケ.md",
                 f"---\nid: {nid}\nauthor: {c.member}\ntype: イシュー\nimpact: 出荷\nspeed: すぐ\n"
                 f"project: [{project}]\n---\n{body}")


def report(c) -> str:
    return text(c.personal / "_仕組み/同期レポート.md")


def test_moves_heavy_and_keeps_light(box):
    yu, data = box["yu"], box["data"]
    note = issue(yu, body="![[_仕組み/attachments/0RB001001/成形条件.xlsx]]\n"
                          "![[_仕組み/attachments/0RB001001/写真.png]]\n[資料](_仕組み/attachments/0RB001001/報告.pdf)\n")
    att = yu.personal / "_仕組み/attachments/0RB001001"
    write(att / "成形条件.xlsx", b"xlsx")
    write(att / "写真.png", b"png")
    write(att / "報告.pdf", b"pdf")
    write(att / "短い.mp4", b"0" * 1000)
    write(att / "長い.mp4", b"0" * (21 * 1024 * 1024))
    run_once(yu, now=NOW)
    # 共有していないノートでも集約はされるが、最初の同期では共有にまだないので _個人 へ
    moved = data / "_個人/Yu/0RB001001/成形条件.xlsx"
    assert moved.read_bytes() == b"xlsx"
    assert (data / "_個人/Yu/0RB001001/長い.mp4").exists()
    assert not (att / "成形条件.xlsx").exists()
    assert (att / "写真.png").exists() and (att / "報告.pdf").exists() and (att / "短い.mp4").exists()
    t = text(note)
    assert f"[成形条件.xlsx]({file_url(moved)})" in t
    assert "![[_仕組み/attachments/0RB001001/写真.png]]" in t       # 画像はそのまま
    assert "重い添付を移した: _仕組み/attachments/0RB001001/成形条件.xlsx → 開発データ/_個人/Yu/0RB001001/成形条件.xlsx" in report(yu)
    # 重い添付は共有 vault にコピーしない
    assert not (box["shared"] / "_仕組み/attachments/0RB001001/成形条件.xlsx").exists()
    assert (box["shared"] / "_仕組み/attachments/0RB001001/写真.png").exists()


def test_promote_to_project_and_shared_link_form(box):
    yu, data, shared = box["yu"], box["data"], box["shared"]
    note = issue(yu, body="![[_仕組み/attachments/0RB001001/成形条件.xlsx]]\n")
    write(yu.personal / "_仕組み/attachments/0RB001001/成形条件.xlsx", b"xlsx")
    run_once(yu, now=NOW)            # _個人 へ移し、ノートを共有へ集める
    run_once(yu, now=NOW + 60)       # 共有されたので プロジェクトへ移す(F-20)
    final = data / PJ / "0RB001001/成形条件.xlsx"
    assert final.read_bytes() == b"xlsx"
    assert not (data / "_個人/Yu/0RB001001/成形条件.xlsx").exists()
    assert f"[成形条件.xlsx]({file_url(final)})" in text(note)
    run_once(yu, now=NOW + 120)      # 書き換えたノートを集める
    s = text(shared / f"{PJ}/03_イシュー/0RB001001_ヒケ.md")
    assert f"[成形条件.xlsx](開発データ/{PJ}/0RB001001/成形条件.xlsx)" in s   # 共有では相対パス(F-19)
    assert "file:///" not in s
    # 佐藤に配るときは、佐藤の PC の file:/// に直す
    run_once(box["sato"], now=NOW + 180)
    got = text(box["sato"].personal / f"90_共有/{PJ}/03_イシュー/0RB001001_ヒケ.md")
    assert f"[成形条件.xlsx]({file_url(box['sato'].shared_data / PJ / '0RB001001/成形条件.xlsx')})" in got
    # 次の同期で、同じ内容とみなされて競合にならない
    run_once(yu, now=NOW + 240)
    run_once(box["sato"], now=NOW + 300)
    assert "競合" not in report(yu) and "競合" not in report(box["sato"])


def test_same_name_gets_suffix(box):
    yu, data = box["yu"], box["data"]
    issue(yu, body="![[_仕組み/attachments/0RB001001/a.xlsx]]\n")
    write(data / "_個人/Yu/0RB001001/a.xlsx", b"old")
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"new")
    run_once(yu, now=NOW)
    assert (data / "_個人/Yu/0RB001001/a.xlsx").read_bytes() == b"old"
    assert (data / "_個人/Yu/0RB001001/a_2.xlsx").read_bytes() == b"new"


def test_no_data_root_reports(box):
    yu = box["yu"]
    yu.shared_data = None
    issue(yu)
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    run_once(yu, now=NOW)
    assert "開発データの場所が設定にありません: 重い添付が 1 件" in report(yu)
    assert (yu.personal / "_仕組み/attachments/0RB001001/a.xlsx").exists()


def test_dry_run_moves_nothing(box):
    yu = box["yu"]
    note = issue(yu, body="![[_仕組み/attachments/0RB001001/a.xlsx]]\n")
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    before = text(note)
    run_once(yu, dry_run=True, now=NOW)
    assert (yu.personal / "_仕組み/attachments/0RB001001/a.xlsx").exists()
    assert text(note) == before
    assert "予定: 重い添付を移した" in report(yu)


def test_link_forms():
    root = Path("C:/Users/yu/Box/開発データ")
    url = file_url(root / "PJ/0RB001001/成形 条件.xlsx")
    assert url == "file:///C:/Users/yu/Box/%E9%96%8B%E7%99%BA%E3%83%87%E3%83%BC%E3%82%BF/PJ/0RB001001/%E6%88%90%E5%BD%A2%20%E6%9D%A1%E4%BB%B6.xlsx"
    s = to_shared(f"見て [条件]({url}) と [他](https://example.com)", root)
    assert s == "見て [条件](<開発データ/PJ/0RB001001/成形 条件.xlsx>) と [他](https://example.com)"
    assert to_personal(s, root) == f"見て [条件]({url}) と [他](https://example.com)"
    # ファイル名だけのリンクは、その id のノートの中だけ直す
    t = "![[成形条件.xlsx]] と ![[_仕組み/attachments/0RB001001/成形条件.xlsx|条件表]]"
    assert relink(t, "0RB001001", "成形条件.xlsx", "U", True) == "[成形条件.xlsx](U) と [条件表](U)"
    assert relink(t, "0RB001001", "成形条件.xlsx", "U", False) == "![[成形条件.xlsx]] と [条件表](U)"


def test_recover_shared(box, capsys):
    from notesync.__main__ import main
    import yaml
    shared, data, yu = box["shared"], box["data"], box["yu"]
    write(shared / f"{PJ}/03_イシュー/直接書いた.md", "---\ntype: イシュー\n---\n[[参考メモ]] を見る\n")
    write(shared / f"{PJ}/03_イシュー/0RB009002_古い.md",
          "---\nid: 0RB009002\nauthor: 佐藤\ntype: イシュー\n---\n![[_仕組み/attachments/0RB009002/測定.csv]]\n")
    write(shared / "_仕組み/attachments/0RB009002/測定.csv", "a,b\n")
    write(shared / "共通/02_ノード/参考メモ.md", "---\ntype: ノード\n---\n")
    run_once(yu, now=NOW)
    r = report(yu)
    assert "拾い直し: 共有 vault に id のないノートが 2 件あります" in r
    assert "拾い直し: 共有 vault の _仕組み/attachments/ に重い添付が 1 件あります" in r
    cfg_path = write(yu.personal.parent / "config.yaml", yaml.safe_dump({
        "member": "Yu", "personal": str(yu.personal), "shared": str(shared), "shared_data": str(data),
        "backup_dir": str(yu.backup_dir), "state_dir": str(yu.state_dir)}, allow_unicode=True))
    assert main(["recover", "--config", str(cfg_path)]) == 0          # 試し運転では変えない
    assert (shared / f"{PJ}/03_イシュー/直接書いた.md").exists()
    assert main(["recover", "--config", str(cfg_path), "--run"]) == 0
    [issue] = (shared / f"{PJ}/03_イシュー").glob("*_直接書いた.md")
    [memo] = (shared / "共通/02_ノード").glob("*_参考メモ.md")
    assert f"[[{memo.stem}|参考メモ]]" in issue.read_text(encoding="utf-8")
    assert (data / PJ / "0RB009002/測定.csv").exists()
    assert not (shared / "_仕組み/attachments/0RB009002/測定.csv").exists()
    old = (shared / f"{PJ}/03_イシュー/0RB009002_古い.md").read_text(encoding="utf-8")
    assert f"[測定.csv](開発データ/{PJ}/0RB009002/測定.csv)" in old
    run_once(yu, now=NOW + 60)
    assert "拾い直し" not in report(yu)
