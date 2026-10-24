"""集約と再配布(F-05〜11、F-14、F-15)。Yu と 佐藤 の2人分の vault で確かめる。"""

from pathlib import Path

import pytest

from notesync.config import Config, member_code
from notesync.run import run_once

from .conftest import text

PJ = "試しPJ"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(body)
    return path


@pytest.fixture
def box(tmp_path):
    root = tmp_path / "Box"
    shared = root / "共有"
    write(shared / "_tools/同期プログラム/メンバー.csv", "名前,記号,使い始めた日\nYu,001,2026-10-24\n佐藤,002,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md", "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [Yu, 佐藤]\n---\n")
    write(shared / "別PJ/0RA00B001_別PJ.md", "---\nid: 0RA00B001\ntype: プロジェクト\nmembers: [Yu]\n---\n")
    write(shared / "別PJ/03_イシュー/0RA00C001_別の話.md",
          "---\nid: 0RA00C001\nauthor: Yu\ntype: イシュー\nproject: [別PJ]\n---\n")

    yu = root / "個人_Yu"
    write(yu / "_記録/私.yaml", 'name: Yu\ncode: "001"\n')
    write(yu / "02_ノード/0RB001001_水.md", "---\nid: 0RB001001\ntype: ノード\n---\n水の話\n")
    write(yu / "03_イシュー/0RB002001_ヒケ.md",
          f"---\nid: 0RB002001\ntype: イシュー\nimpact: 出荷\nproject: [{PJ}]\n---\n[[0RB001001_水|水]] が原因\n")
    write(yu / "04_タスク/0RB003001_保圧を変える.md",
          '---\nid: 0RB003001\ntype: タスク\nparent: ["[[0RB002001_ヒケ|ヒケ]]"]\n---\n')
    write(yu / "_attachments/0RB003001/図.excalidraw.md", "図のデータ\n")
    write(yu / "02_ノード/0RB004001_秘密のメモ.md", "---\nid: 0RB004001\ntype: ノード\nvisibility: 個人\n---\n")
    write(yu / "05_結果/0RB005001_保圧のナレッジ.md",
          '---\nid: 0RB005001\ntype: ナレッジ\nparent: ["[[0RB003001_保圧を変える|保圧を変える]]"]\n'
          'risk_reduction:\n  - "[[0RB002001_ヒケ]] 出荷→小"\nusefulness: B\n---\n')
    write(yu / "03_イシュー/0RB006001_迷子.md", "---\nid: 0RB006001\ntype: イシュー\nproject: [無いPJ]\n---\n")
    write(yu / "02_ノード/0RB007001_顧客の寸法.md",
          "---\nid: 0RB007001\ntype: ノード\n---\n[[0RC001001_顧客図面]] を見た\n")

    sato = root / "個人_佐藤"
    write(sato / "_記録/私.yaml", 'name: 佐藤\ncode: "002"\n')
    write(sato / "02_ノード/0RB101002_鉄.md", "---\nid: 0RB101002\ntype: ノード\n---\n")

    secret = root / "機密_顧客A"
    write(secret / "06_事実/0RC001001_顧客図面.md", "---\nid: 0RC001001\n---\n")

    def cfg(member):
        c = Config(member=member, personal=root / f"個人_{member}", shared=shared,
                   secret=[secret], backup_dir=tmp_path / f"backup_{member}",
                   state_dir=tmp_path / f"state_{member}", idle_seconds=0)
        c.code = member_code(c)
        return c

    return {"root": root, "shared": shared, "yu": cfg("Yu"), "sato": cfg("佐藤")}


def files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def report(c) -> str:
    return text(c.personal / "00_同期レポート.md")


def test_collects_by_type_and_project(box):
    run_once(box["yu"])
    s = files(box["shared"])
    assert "共通/02_ノード/0RB001001_水.md" in s
    assert f"{PJ}/03_イシュー/0RB002001_ヒケ.md" in s
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in s       # parent のイシューのプロジェクトへ
    assert "_attachments/0RB003001/図.excalidraw.md" in s           # 添付は同じパスへ(F-07)
    # 共有したノートには author が入っている
    assert "author: Yu" in text(box["shared"] / "共通/02_ノード/0RB001001_水.md")


def test_does_not_collect_when_conditions_fail(box):
    run_once(box["yu"])
    s = " ".join(files(box["shared"]))
    r = report(box["yu"])
    todo = r.split("## 警告")[0]
    assert "秘密のメモ" not in s and "秘密のメモ" not in todo     # visibility 個人は知らせもしない
    assert "保圧のナレッジ" not in s
    assert "保圧のナレッジ|保圧のナレッジ]] の reviewed_by が空です" in r
    assert "迷子" not in s and "プロジェクト「無いPJ」の台帳が共有 vault にありません" in r
    assert "顧客の寸法" not in s and "機密へのリンク" in r          # F-40


def test_knowledge_of_big_issue_needs_another_reviewer(box):
    k = box["yu"].personal / "05_結果/0RB005001_保圧のナレッジ.md"
    write(k, text(k).replace("usefulness: B", "usefulness: B\nreviewed_by: [Yu]"))
    run_once(box["yu"])
    assert "確認待ち" in report(box["yu"])
    write(k, text(k).replace("reviewed_by: [Yu]", "reviewed_by: [Yu, 佐藤]"))
    run_once(box["yu"])
    assert f"{PJ}/05_結果/0RB005001_保圧のナレッジ.md" in files(box["shared"])


def test_redistributes_to_members_only(box):
    run_once(box["yu"])
    run_once(box["sato"])
    got = files(box["sato"].personal / "90_共有")
    assert "共通/02_ノード/0RB001001_水.md" in got
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in got
    assert f"{PJ}/0RA00A001_{PJ}.md" in got
    assert not any(x.startswith("別PJ/") for x in got)            # 佐藤は 別PJ のメンバーでない
    assert (box["sato"].personal / "_attachments/0RB003001/図.excalidraw.md").exists()
    # 自分が書いたノートは配らない(F-10)
    run_once(box["yu"])
    assert not any("0RB001001" in x for x in files(box["yu"].personal / "90_共有"))
    assert "鉄" in " ".join(files(box["yu"].personal / "90_共有"))


def test_second_run_changes_nothing(box):
    for _ in range(2):
        run_once(box["yu"])
        run_once(box["sato"])
    before = {p: text(box["root"] / p) for p in files(box["root"])}
    run_once(box["yu"])
    run_once(box["sato"])
    after = {p: text(box["root"] / p) for p in files(box["root"]) if not p.endswith("00_同期レポート.md")}
    assert after == {p: v for p, v in before.items() if not p.endswith("00_同期レポート.md")}


def test_update_flows_through(box):
    run_once(box["yu"])
    run_once(box["sato"])
    water = box["yu"].personal / "02_ノード/0RB001001_水.md"
    write(water, text(water) + "0℃で凍る\n")
    run_once(box["yu"])
    run_once(box["sato"])
    copy = box["sato"].personal / "90_共有/共通/02_ノード/0RB001001_水.md"
    assert "0℃で凍る" in text(copy)


def test_adopted_note_comes_back_to_author(box):
    """佐藤が 90_共有/ から自分のフォルダへ移して書き足すと、共有を経て Yu のノートに入る。"""
    run_once(box["yu"])
    run_once(box["sato"])
    src = box["sato"].personal / "90_共有/共通/02_ノード/0RB001001_水.md"
    dest = box["sato"].personal / "02_ノード/0RB001001_水.md"
    src.rename(dest)
    write(dest, text(dest) + "佐藤の書き足し\n")
    run_once(box["sato"])
    assert "佐藤の書き足し" in text(box["shared"] / "共通/02_ノード/0RB001001_水.md")
    run_once(box["yu"])
    assert "佐藤の書き足し" in text(box["yu"].personal / "02_ノード/0RB001001_水.md")
    assert "取り込み" in report(box["yu"])


def test_conflict_keeps_both_and_resolves(box):
    run_once(box["yu"])
    shared_water = box["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "共有で直接の書き足し\n")
    water = box["yu"].personal / "02_ノード/0RB001001_水.md"
    write(water, text(water) + "Yu の書き足し\n")
    run_once(box["yu"])
    conflicts = [p for p in shared_water.parent.iterdir() if "_競合_Yu_" in p.name]
    assert len(conflicts) == 1 and "Yu の書き足し" in text(conflicts[0])
    assert "共有で直接の書き足し" in text(shared_water)               # 上書きしない
    assert "Yu の書き足し" not in text(shared_water)
    assert "競合: 共有/共通/02_ノード/0RB001001_水.md" in report(box["yu"])
    # 次の回も競合ファイルを増やさない
    run_once(box["yu"])
    assert len([p for p in shared_water.parent.iterdir() if "_競合_" in p.name]) == 1
    # 共有側でまとめると、個人に入って競合が消える
    write(shared_water, text(shared_water) + "Yu の書き足し\n")
    run_once(box["yu"])
    assert text(water) == text(shared_water)
    assert "競合: 共有" not in report(box["yu"]).split("## 警告")[0]


def test_conflict_file_is_not_redistributed(box):
    run_once(box["yu"])
    shared_water = box["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "a\n")
    water = box["yu"].personal / "02_ノード/0RB001001_水.md"
    write(water, text(water) + "b\n")
    run_once(box["yu"])
    run_once(box["sato"])
    assert not any("_競合_" in x for x in files(box["sato"].personal))


def test_editing_distributed_copy_is_reported(box):
    run_once(box["yu"])
    run_once(box["sato"])
    copy = box["sato"].personal / "90_共有/共通/02_ノード/0RB001001_水.md"
    write(copy, text(copy) + "ここに書いてしまった\n")
    run_once(box["sato"])
    assert "90_共有 の編集" in report(box["sato"])
    assert "ここに書いてしまった" not in text(box["shared"] / "共通/02_ノード/0RB001001_水.md")


def test_archive_move_is_reflected(box):
    run_once(box["yu"])
    src = box["yu"].personal / "04_タスク/0RB003001_保圧を変える.md"
    dest = box["yu"].personal / "99_archive/0RB003001_保圧を変える.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    run_once(box["yu"])
    s = files(box["shared"])
    assert "99_archive/0RB003001_保圧を変える.md" in s
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" not in s


def test_same_id_other_note_is_not_collected(box):
    write(box["shared"] / "共通/02_ノード/0RB001001_ちがう水.md",
          "---\nid: 0RB001001\nauthor: 佐藤\ntype: ノード\n---\n")
    run_once(box["yu"])
    assert "0RB001001_水.md" not in " ".join(files(box["shared"]))
    assert "同じ id: 0RB001001" in report(box["yu"])


def test_dry_run_writes_only_report(box):
    before = files(box["root"])
    run_once(box["yu"], dry_run=True)
    after = files(box["root"])
    assert after - before == {"個人_Yu/00_同期レポート.md"}
    r = report(box["yu"])
    assert "予定: 集約: 02_ノード/0RB001001_水.md → 共有/共通/02_ノード/0RB001001_水.md" in r
    assert not box["yu"].state_path.exists()


def test_lost_state_is_rebuilt_without_overwriting(box):
    """F-34: 記録が消えても、同じなら同期済み、違えば競合にする。"""
    run_once(box["yu"])
    box["yu"].state_path.unlink()
    run_once(box["yu"])
    assert "競合" not in report(box["yu"]).split("## 記録")[0].replace("(なし)", "")
    shared_water = box["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "x\n")
    box["yu"].state_path.unlink()
    run_once(box["yu"])
    assert "x\n" in text(shared_water)
    assert any("_競合_" in p.name for p in shared_water.parent.iterdir())
