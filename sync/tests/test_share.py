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
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv", "名前,記号,使い始めた日\nYu,001,2026-10-24\n佐藤,002,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md", "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [Yu, 佐藤]\n---\n")
    write(shared / "別PJ/0RA00B001_別PJ.md", "---\nid: 0RA00B001\ntype: プロジェクト\nmembers: [Yu]\n---\n")
    write(shared / "別PJ/03_イシュー/0RA00C001_別の話.md",
          "---\nid: 0RA00C001\nauthor: Yu\ntype: イシュー\nproject: [別PJ]\n---\n")

    yu = root / "個人_Yu"
    write(yu / "_仕組み/記録/私.yaml", 'name: Yu\ncode: "001"\n')
    write(yu / "02_ノード/0RB001001_水.md", "---\nid: 0RB001001\ntype: ノード\n---\n水の話\n")
    write(yu / "03_イシュー/0RB002001_ヒケ.md",
          f"---\nid: 0RB002001\ntype: イシュー\nimpact: 出荷\nproject: [{PJ}]\n---\n[[0RB001001_水|水]] が原因\n")
    write(yu / "04_タスク/0RB003001_保圧を変える.md",
          '---\nid: 0RB003001\ntype: タスク\nparent: ["[[0RB002001_ヒケ|ヒケ]]"]\n---\n')
    write(yu / "_仕組み/attachments/0RB003001/図.excalidraw.md", "図のデータ\n")
    write(yu / "02_ノード/0RB004001_秘密のメモ.md", "---\nid: 0RB004001\ntype: ノード\nvisibility: 個人\n---\n")
    write(yu / "05_ナレッジ/0RB005001_保圧のナレッジ.md",
          '---\nid: 0RB005001\ntype: ナレッジ\nparent: ["[[0RB003001_保圧を変える|保圧を変える]]"]\n'
          'risk_reduction:\n  - "[[0RB002001_ヒケ]] 出荷→小"\nusefulness: B\n---\n')
    write(yu / "03_イシュー/0RB006001_迷子.md", "---\nid: 0RB006001\ntype: イシュー\nproject: [無いPJ]\n---\n")
    write(yu / "02_ノード/0RB007001_顧客の寸法.md",
          "---\nid: 0RB007001\ntype: ノード\n---\n[[0RC001001_顧客図面]] を見た\n")

    sato = root / "個人_佐藤"
    write(sato / "_仕組み/記録/私.yaml", 'name: 佐藤\ncode: "002"\n')
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
    return text(c.personal / "_仕組み/同期レポート.md")


def test_collects_by_type_and_project(box):
    run_once(box["yu"])
    s = files(box["shared"])
    assert "共通/02_ノード/0RB001001_水.md" in s
    assert f"{PJ}/03_イシュー/0RB002001_ヒケ.md" in s
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in s       # parent のイシューのプロジェクトへ
    assert "_仕組み/attachments/0RB003001/図.excalidraw.md" in s           # 添付は同じパスへ(F-07)
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
    k = box["yu"].personal / "05_ナレッジ/0RB005001_保圧のナレッジ.md"
    write(k, text(k).replace("usefulness: B", "usefulness: B\nreviewed_by: [Yu]"))
    run_once(box["yu"])
    assert "確認待ち" in report(box["yu"])
    write(k, text(k).replace("reviewed_by: [Yu]", "reviewed_by: [Yu, 佐藤]"))
    run_once(box["yu"])
    assert f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md" in files(box["shared"])


def test_redistributes_to_members_only(box):
    run_once(box["yu"])
    run_once(box["sato"])
    got = files(box["sato"].personal / "90_共有")
    assert "共通/02_ノード/0RB001001_水.md" in got
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in got
    assert f"{PJ}/0RA00A001_{PJ}.md" in got
    assert not any(x.startswith("別PJ/") for x in got)            # 佐藤は 別PJ のメンバーでない
    assert (box["sato"].personal / "_仕組み/attachments/0RB003001/図.excalidraw.md").exists()
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
    after = {p: text(box["root"] / p) for p in files(box["root"]) if not p.endswith("_仕組み/同期レポート.md")}
    assert after == {p: v for p, v in before.items() if not p.endswith("_仕組み/同期レポート.md")}


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
    assert after - before == {"個人_Yu/_仕組み/同期レポート.md"}
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


# ---------- F-47: 名前か別名が重なるノード ----------

def add_h2o(box):
    """佐藤の「蒸留水」(別名 H2O)が共有にあり、Yu が別に「H2O」を作った。"""
    sato = box["sato"].personal
    write(sato / "02_ノード/0RB102002_蒸留水.md",
          "---\nid: 0RB102002\ntype: ノード\naliases:\n  - 蒸留水\n  - H2O\n---\n## これは何か\n佐藤のメモ\n")
    run_once(box["sato"])
    yu = box["yu"].personal
    write(yu / "02_ノード/0RB008001_H2O.md",
          "---\nid: 0RB008001\ntype: ノード\naliases: [H2O, 純水]\n---\n## これは何か\n"
          "Yuのメモ ![[写真.png]]\n## 何に影響するか\n")
    write(yu / "_仕組み/attachments/0RB008001/写真.png", "png")
    write(yu / "03_イシュー/0RB009001_濁り.md",
          f"---\nid: 0RB009001\ntype: イシュー\nproject: [{PJ}]\n---\n[[0RB008001_H2O|H2O]] と [[0RB008001_H2O]]\n")


def tick(c, word):
    p = c.personal / "_仕組み/同期レポート.md"
    lines = [l.replace("- [ ]", "- [x]", 1) if l.startswith(f"- [ ] {word}:") and "0RB008001" in l else l
             for l in text(p).splitlines()]
    write(p, "\n".join(lines) + "\n")


def test_overlapping_node_is_asked_not_collected(box):
    add_h2o(box)
    run_once(box["yu"])
    assert not any("0RB008001" in f for f in files(box["shared"]))
    r = report(box["yu"])
    assert "- [ ] 同じもの: [[0RB008001_H2O|H2O]] を [[0RB102002_蒸留水|蒸留水]](佐藤) にまとめる" in r
    assert "- [ ] 別もの: [[0RB008001_H2O|H2O]] と [[0RB102002_蒸留水|蒸留水]](佐藤)" in r
    assert "同じ名前:" not in r                           # F-04 と二重に聞かない


def test_same_merges_into_shared_node(box):
    add_h2o(box)
    run_once(box["yu"])
    tick(box["yu"], "同じもの")
    run_once(box["yu"], dry_run=True)                     # 試し運転では答えを消さない
    assert "- [x] 同じもの:" in report(box["yu"])
    run_once(box["yu"])
    yu, shared = box["yu"].personal, box["shared"]
    water = text(shared / "共通/02_ノード/0RB102002_蒸留水.md")
    assert 'aliases: ["蒸留水", "H2O", "純水"]' in water
    assert "  - H2O" not in water                      # 縦に並んだ別名を残さない
    assert 'author: ["佐藤", "Yu"]' in water
    assert "## まとめたメモ(H2O、Yu、" in water
    assert "- [ ] Yu: 「H2O」のメモを上の本文に書き直して、この章を消す 📅 " in water
    assert "### これは何か\nYuのメモ" in water and "何に影響するか" not in water
    assert (shared / "_仕組み/attachments/0RB102002/写真.png").exists()
    # 自分のノードは archive へ、リンクは付け替え
    assert not (yu / "02_ノード/0RB008001_H2O.md").exists()
    assert 'merged_into: "[[0RB102002_蒸留水|蒸留水]]"' in text(yu / "99_archive/0RB008001_H2O.md")
    issue = text(yu / "03_イシュー/0RB009001_濁り.md")
    assert "[[0RB102002_蒸留水|H2O]] と [[0RB102002_蒸留水|H2O]]" in issue
    assert "同じもの:" not in report(box["yu"])
    # Yu も author に入ったが、最初に書いたのは佐藤なので Yu にも配られる。佐藤の手元にも入る
    run_once(box["yu"])
    assert "## まとめたメモ" in text(yu / "90_共有/共通/02_ノード/0RB102002_蒸留水.md")
    run_once(box["sato"])
    assert "## まとめたメモ" in text(box["sato"].personal / "02_ノード/0RB102002_蒸留水.md")
    assert "同じ名前:" not in report(box["yu"])


def test_other_keeps_both_and_stops_asking(box):
    add_h2o(box)
    run_once(box["yu"])
    tick(box["yu"], "別もの")
    run_once(box["yu"])
    assert "共通/02_ノード/0RB008001_H2O.md" in files(box["shared"])
    run_once(box["yu"])
    r = report(box["yu"])
    assert "別もの:" not in r and "同じもの:" not in r and "同じ名前:" not in r


def test_skips_while_other_pc_syncs(box):
    """同じ個人 vault を別の PC が同期している間は、その回を見送る(複数の PC で使う)。"""
    import json
    import time as _t
    lock = box["yu"].lock_path
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pc": "WORK-PC", "time": _t.time()}), encoding="utf-8")
    before = files(box["root"])
    r = run_once(box["yu"])
    assert r.skipped == "WORK-PC"
    assert files(box["root"]) == before
    lock.unlink()
    run_once(box["yu"])
    assert not lock.exists()
    assert (box["shared"] / "共通/02_ノード/0RB001001_水.md").exists()


def test_design_options_go_to_their_own_folder(box):
    """設計案は 01_設計案/ へ集める。古い type(ソリューション・設計記録)も同じ(仕様書 v0.54)。"""
    yu = box["yu"].personal
    write(yu / "01_目的/0RB201001_予兆検知.md", f"---\nid: 0RB201001\ntype: 目的\nproject: [{PJ}]\n---\n")
    goal = '["[[0RB201001_予兆検知|予兆検知]]"]'
    write(yu / "01_設計案/0RB202001_A案.md", f"---\nid: 0RB202001\ntype: 設計案\nparent: {goal}\n---\n")
    write(yu / "01_目的/0RB203001_B案.md", f"---\nid: 0RB203001\ntype: ソリューション\nparent: {goal}\n---\n")
    run_once(box["yu"])
    s = files(box["shared"])
    assert f"{PJ}/01_目的/0RB201001_予兆検知.md" in s
    assert f"{PJ}/01_設計案/0RB202001_A案.md" in s
    assert f"{PJ}/01_設計案/0RB203001_B案.md" in s
