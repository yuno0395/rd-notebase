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
def cloud(tmp_path):
    root = tmp_path / "Box"
    shared = root / "共有"
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv", "名前,記号,使い始めた日\nYu,001,2026-10-24\n佐藤,002,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md", "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [Yu, 佐藤]\n---\n")
    write(shared / "別PJ/0RA00B001_別PJ.md", "---\nid: 0RA00B001\ntype: プロジェクト\nmembers: [Yu]\n---\n")
    write(shared / "別PJ/03_イシュー/0RA00C001_別の話.md",
          "---\nid: 0RA00C001\nauthor: Yu\ntype: イシュー\nproject: [別PJ]\n---\n")

    yu = root / "個人_Yu"
    write(yu / "_仕組み/個人設定.md", '---\nname: Yu\n---\n')
    write(yu / "共通/02_ノード/0RB001001_水.md", "---\nid: 0RB001001\ntype: ノード\n---\n水の話\n")
    write(yu / f"{PJ}/03_イシュー/0RB002001_ヒケ.md",
          f"---\nid: 0RB002001\ntype: イシュー\nimpact: 出荷\nproject: [{PJ}]\n---\n[[0RB001001_水|水]] が原因\n")
    write(yu / f"{PJ}/04_タスク/0RB003001_保圧を変える.md",
          '---\nid: 0RB003001\ntype: タスク\nparent: ["[[0RB002001_ヒケ|ヒケ]]"]\n---\n')
    write(yu / "_仕組み/attachments/0RB003001/図.excalidraw.md", "図のデータ\n")
    write(yu / "共通/02_ノード/0RB004001_秘密のメモ.md", "---\nid: 0RB004001\ntype: ノード\nvisibility: 個人\n---\n")
    write(yu / "00_日誌/メモ/2026-10-29 思いつき.md", MEMO)
    write(yu / f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md",
          '---\nid: 0RB005001\ntype: ナレッジ\nparent: ["[[0RB003001_保圧を変える|保圧を変える]]"]\n'
          'risk_reduction:\n  - "[[0RB002001_ヒケ]] 出荷→小"\nusefulness: B\n---\n')
    write(yu / "03_イシュー/0RB006001_迷子.md", "---\nid: 0RB006001\ntype: イシュー\nproject: [無いPJ]\n---\n")
    write(yu / "共通/02_ノード/0RB007001_顧客の寸法.md",
          "---\nid: 0RB007001\ntype: ノード\n---\n[[0RC001001_顧客図面]] を見た\n")

    sato = root / "個人_佐藤"
    write(sato / "_仕組み/個人設定.md", '---\nname: 佐藤\n---\n')
    write(sato / "共通/02_ノード/0RB101002_鉄.md", "---\nid: 0RB101002\ntype: ノード\n---\n")

    secret = root / "機密_顧客A"
    (secret / "_仕組み").mkdir(parents=True)
    write(secret / "06_事実/0RC001001_顧客図面.md", "---\nid: 0RC001001\n---\n")

    def cfg(member):
        c = Config(member=member, personal=root / f"個人_{member}", shared=shared,
                   secret=[secret], backup_dir=tmp_path / f"backup_{member}",
                   state_dir=tmp_path / f"state_{member}", idle_seconds=0)
        c.code = member_code(c)
        return c

    return {"root": root, "shared": shared, "yu": cfg("Yu"), "sato": cfg("佐藤")}


MEMO = "---\ntype: メモ\nvisibility: 個人\n---\n[[0RB001001_水|水]] を温めたら?\n"


def files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def report(c) -> str:
    return text(c.personal / "_仕組み/同期レポート.md")


def test_collects_by_type_and_project(cloud):
    run_once(cloud["yu"])
    s = files(cloud["shared"])
    assert "共通/02_ノード/0RB001001_水.md" in s
    assert f"{PJ}/03_イシュー/0RB002001_ヒケ.md" in s
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in s       # parent のイシューのプロジェクトへ
    assert "_仕組み/attachments/0RB003001/図.excalidraw.md" in s           # 添付は同じパスへ(F-07)
    # 共有したノートには author が入っている
    assert "author: Yu" in text(cloud["shared"] / "共通/02_ノード/0RB001001_水.md")


def test_does_not_collect_when_conditions_fail(cloud):
    run_once(cloud["yu"])
    s = " ".join(files(cloud["shared"]))
    r = report(cloud["yu"])
    todo = r.split("## 警告")[0]
    assert "秘密のメモ" not in s and "秘密のメモ" not in todo     # visibility 個人は知らせもしない
    assert "思いつき" not in s and "思いつき" not in r                 # 共有しないメモ(00_日誌/メモ/)
    assert text(cloud["yu"].personal / "00_日誌/メモ/2026-10-29 思いつき.md") == MEMO  # id もつけない
    assert "保圧のナレッジ" not in s
    assert "保圧のナレッジ|保圧のナレッジ]] の reviewed_by が空です" in r
    assert "迷子" not in s and "プロジェクト「無いPJ」の台帳が共有 vault にありません" in r
    assert "顧客の寸法" not in s and "機密へのリンク" in r          # F-40


def test_knowledge_of_big_issue_needs_another_reviewer(cloud):
    k = cloud["yu"].personal / f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md"
    write(k, text(k).replace("usefulness: B", "usefulness: B\nreviewed_by: [Yu]"))
    run_once(cloud["yu"])
    assert "確認待ち" in report(cloud["yu"])
    write(k, text(k).replace("reviewed_by: [Yu]", "reviewed_by: [Yu, 佐藤]"))
    run_once(cloud["yu"])
    assert f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md" in files(cloud["shared"])


def test_redistributes_to_members_only(cloud):
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    got = files(cloud["sato"].personal)                            # 共有と同じ場所に配る
    assert "共通/02_ノード/0RB001001_水.md" in got
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in got
    assert f"{PJ}/0RA00A001_{PJ}.md" in got
    assert not any(x.startswith("別PJ/") for x in got)            # 佐藤は 別PJ のメンバーでない
    assert (cloud["sato"].personal / "_仕組み/attachments/0RB003001/図.excalidraw.md").exists()
    # 自分が書いたノートは配らない(F-10)
    run_once(cloud["yu"])
    assert [x for x in files(cloud["yu"].personal) if "0RB001001" in x] == ["共通/02_ノード/0RB001001_水.md"]
    assert "共通/02_ノード/0RB101002_鉄.md" in files(cloud["yu"].personal)
    assert not (cloud["yu"].personal / "90_共有").exists()


def test_second_run_changes_nothing(cloud):
    for _ in range(2):
        run_once(cloud["yu"])
        run_once(cloud["sato"])
    before = {p: text(cloud["root"] / p) for p in files(cloud["root"])}
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    after = {p: text(cloud["root"] / p) for p in files(cloud["root"]) if not p.endswith("_仕組み/同期レポート.md")}
    assert after == {p: v for p, v in before.items() if not p.endswith("_仕組み/同期レポート.md")}


def test_update_flows_through(cloud):
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    water = cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md"
    write(water, text(water) + "0℃で凍る\n")
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    copy = cloud["sato"].personal / "共通/02_ノード/0RB001001_水.md"
    assert "0℃で凍る" in text(copy)


def test_adopted_note_comes_back_to_author(cloud):
    """佐藤が配られたノートの author に自分を足して書き足すと、共有を経て Yu のノートに入る。"""
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    dest = cloud["sato"].personal / "共通/02_ノード/0RB001001_水.md"
    write(dest, text(dest).replace("author: Yu", 'author: ["Yu", "佐藤"]') + "佐藤の書き足し\n")
    run_once(cloud["sato"])
    assert "佐藤の書き足し" in text(cloud["shared"] / "共通/02_ノード/0RB001001_水.md")
    run_once(cloud["yu"])
    assert "佐藤の書き足し" in text(cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md")
    assert "取り込み" in report(cloud["yu"])
    assert 'author: ["Yu", "佐藤"]' in text(cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md")


def test_conflict_keeps_both_and_resolves(cloud):
    run_once(cloud["yu"])
    shared_water = cloud["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "共有で直接の書き足し\n")
    water = cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md"
    write(water, text(water) + "Yu の書き足し\n")
    run_once(cloud["yu"])
    conflicts = [p for p in shared_water.parent.iterdir() if "_競合_Yu_" in p.name]
    assert len(conflicts) == 1 and "Yu の書き足し" in text(conflicts[0])
    assert "共有で直接の書き足し" in text(shared_water)               # 上書きしない
    assert "Yu の書き足し" not in text(shared_water)
    assert "競合: 共有/共通/02_ノード/0RB001001_水.md" in report(cloud["yu"])
    # 次の回も競合ファイルを増やさない
    run_once(cloud["yu"])
    assert len([p for p in shared_water.parent.iterdir() if "_競合_" in p.name]) == 1
    # 共有側でまとめると、個人に入って競合が消える
    write(shared_water, text(shared_water) + "Yu の書き足し\n")
    run_once(cloud["yu"])
    assert text(water) == text(shared_water)
    assert "競合: 共有" not in report(cloud["yu"]).split("## 警告")[0]


def test_conflict_file_is_not_redistributed(cloud):
    run_once(cloud["yu"])
    shared_water = cloud["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "a\n")
    water = cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md"
    write(water, text(water) + "b\n")
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    assert not any("_競合_" in x for x in files(cloud["sato"].personal))


def test_editing_others_note_is_put_back(cloud):
    run_once(cloud["yu"])
    run_once(cloud["sato"])
    copy = cloud["sato"].personal / "共通/02_ノード/0RB001001_水.md"
    write(copy, text(copy) + "ここに書いてしまった\n")
    run_once(cloud["sato"])
    assert "他の人のノート: 共通/02_ノード/0RB001001_水.md が手元で変わっていた" in report(cloud["sato"])
    assert "ここに書いてしまった" not in text(cloud["shared"] / "共通/02_ノード/0RB001001_水.md")
    assert "ここに書いてしまった" not in text(copy)                 # 共有の中身に戻す
    assert list((cloud["sato"].personal.parent.parent / "backup_佐藤").rglob("0RB001001_水.md"))


def test_archive_move_is_reflected(cloud):
    run_once(cloud["yu"])
    src = cloud["yu"].personal / f"{PJ}/04_タスク/0RB003001_保圧を変える.md"
    dest = cloud["yu"].personal / "99_archive/0RB003001_保圧を変える.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    run_once(cloud["yu"])
    s = files(cloud["shared"])
    assert "99_archive/0RB003001_保圧を変える.md" in s
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" not in s


def test_same_id_other_note_is_not_collected(cloud):
    write(cloud["shared"] / "共通/02_ノード/0RB001001_ちがう水.md",
          "---\nid: 0RB001001\nauthor: 佐藤\ntype: ノード\n---\n")
    run_once(cloud["yu"])
    assert "0RB001001_水.md" not in " ".join(files(cloud["shared"]))
    assert "同じ id: 0RB001001" in report(cloud["yu"])


def test_dry_run_writes_only_report(cloud):
    before = files(cloud["root"])
    run_once(cloud["yu"], dry_run=True)
    after = files(cloud["root"])
    assert after - before == {"個人_Yu/_仕組み/同期レポート.md"}
    r = report(cloud["yu"])
    assert "予定: 集約: 共通/02_ノード/0RB001001_水.md → 共有/共通/02_ノード/0RB001001_水.md" in r
    assert not cloud["yu"].state_path.exists()


def test_lost_state_is_rebuilt_without_overwriting(cloud):
    """F-34: 記録が消えても、同じなら同期済み、違えば競合にする。"""
    run_once(cloud["yu"])
    cloud["yu"].state_path.unlink()
    run_once(cloud["yu"])
    assert "競合" not in report(cloud["yu"]).split("## 記録")[0].replace("(なし)", "")
    shared_water = cloud["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "x\n")
    cloud["yu"].state_path.unlink()
    run_once(cloud["yu"])
    assert "x\n" in text(shared_water)
    assert any("_競合_" in p.name for p in shared_water.parent.iterdir())


# ---------- F-47: 名前か別名が重なるノード ----------

def add_h2o(cloud):
    """佐藤の「蒸留水」(別名 H2O)が共有にあり、Yu が別に「H2O」を作った。"""
    sato = cloud["sato"].personal
    write(sato / "共通/02_ノード/0RB102002_蒸留水.md",
          "---\nid: 0RB102002\ntype: ノード\naliases:\n  - 蒸留水\n  - H2O\n---\n## これは何か\n佐藤のメモ\n")
    run_once(cloud["sato"])
    yu = cloud["yu"].personal
    write(yu / "共通/02_ノード/0RB008001_H2O.md",
          "---\nid: 0RB008001\ntype: ノード\naliases: [H2O, 純水]\n---\n## これは何か\n"
          "Yuのメモ ![[写真.png]]\n## 何に影響するか\n")
    write(yu / "_仕組み/attachments/0RB008001/写真.png", "png")
    write(yu / f"{PJ}/03_イシュー/0RB009001_濁り.md",
          f"---\nid: 0RB009001\ntype: イシュー\nproject: [{PJ}]\n---\n[[0RB008001_H2O|H2O]] と [[0RB008001_H2O]]\n")


def tick(c, word):
    p = c.personal / "_仕組み/同期レポート.md"
    lines = [l.replace("- [ ]", "- [x]", 1) if l.startswith(f"- [ ] {word}:") and "0RB008001" in l else l
             for l in text(p).splitlines()]
    write(p, "\n".join(lines) + "\n")


def test_overlapping_node_is_asked_not_collected(cloud):
    add_h2o(cloud)
    run_once(cloud["yu"])
    assert not any("0RB008001" in f for f in files(cloud["shared"]))
    r = report(cloud["yu"])
    assert "- [ ] 同じもの: [[0RB008001_H2O|H2O]] を [[0RB102002_蒸留水|蒸留水]](佐藤) にまとめる" in r
    assert "- [ ] 別もの: [[0RB008001_H2O|H2O]] と [[0RB102002_蒸留水|蒸留水]](佐藤)" in r
    assert "同じ名前:" not in r                           # F-04 と二重に聞かない


def test_same_merges_into_shared_node(cloud):
    add_h2o(cloud)
    run_once(cloud["yu"])
    tick(cloud["yu"], "同じもの")
    run_once(cloud["yu"], dry_run=True)                     # 試し運転では答えを消さない
    assert "- [x] 同じもの:" in report(cloud["yu"])
    run_once(cloud["yu"])
    yu, shared = cloud["yu"].personal, cloud["shared"]
    water = text(shared / "共通/02_ノード/0RB102002_蒸留水.md")
    assert 'aliases: ["蒸留水", "H2O", "純水"]' in water
    assert "  - H2O" not in water                      # 縦に並んだ別名を残さない
    assert 'author: ["佐藤", "Yu"]' in water
    assert "## まとめたメモ(H2O、Yu、" in water
    assert "- [ ] Yu: 「H2O」のメモを上の本文に書き直して、この章を消す 📅 " in water
    assert "### これは何か\nYuのメモ" in water and "何に影響するか" not in water
    assert (shared / "_仕組み/attachments/0RB102002/写真.png").exists()
    # 自分のノードは archive へ、リンクは付け替え
    assert not (yu / "共通/02_ノード/0RB008001_H2O.md").exists()
    assert 'merged_into: "[[0RB102002_蒸留水|蒸留水]]"' in text(yu / "99_archive/0RB008001_H2O.md")
    issue = text(yu / f"{PJ}/03_イシュー/0RB009001_濁り.md")
    assert "[[0RB102002_蒸留水|H2O]] と [[0RB102002_蒸留水|H2O]]" in issue
    assert "同じもの:" not in report(cloud["yu"])
    # Yu も author に入ったが、最初に書いたのは佐藤なので Yu にも配られる。佐藤の手元にも入る
    run_once(cloud["yu"])
    assert "## まとめたメモ" in text(yu / "共通/02_ノード/0RB102002_蒸留水.md")
    run_once(cloud["sato"])
    assert "## まとめたメモ" in text(cloud["sato"].personal / "共通/02_ノード/0RB102002_蒸留水.md")
    assert "同じ名前:" not in report(cloud["yu"])


def test_other_keeps_both_and_stops_asking(cloud):
    add_h2o(cloud)
    run_once(cloud["yu"])
    tick(cloud["yu"], "別もの")
    run_once(cloud["yu"])
    assert "共通/02_ノード/0RB008001_H2O.md" in files(cloud["shared"])
    run_once(cloud["yu"])
    r = report(cloud["yu"])
    assert "別もの:" not in r and "同じもの:" not in r and "同じ名前:" not in r


def test_skips_while_other_pc_syncs(cloud):
    """同じ個人 vault を別の PC が同期している間は、その回を見送る(複数の PC で使う)。"""
    import json
    import time as _t
    lock = cloud["yu"].lock_path
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pc": "WORK-PC", "time": _t.time()}), encoding="utf-8")
    before = files(cloud["root"])
    r = run_once(cloud["yu"])
    assert r.skipped == "WORK-PC"
    assert files(cloud["root"]) == before
    lock.unlink()
    run_once(cloud["yu"])
    assert not lock.exists()
    assert (cloud["shared"] / "共通/02_ノード/0RB001001_水.md").exists()


def test_design_options_go_to_their_own_folder(cloud):
    """設計案は 01_設計案/ へ集める(仕様書 v0.54)。目的の場所にあっても 01_設計案/ へ。"""
    yu = cloud["yu"].personal
    write(yu / "01_目的/0RB201001_予兆検知.md", f"---\nid: 0RB201001\ntype: 目的\nproject: [{PJ}]\n---\n")
    goal = '["[[0RB201001_予兆検知|予兆検知]]"]'
    write(yu / "01_設計案/0RB202001_A案.md", f"---\nid: 0RB202001\ntype: 設計案\nparent: {goal}\n---\n")
    write(yu / "01_目的/0RB203001_B案.md", f"---\nid: 0RB203001\ntype: 設計案\nparent: {goal}\n---\n")
    run_once(cloud["yu"])
    s = files(cloud["shared"])
    assert f"{PJ}/01_目的/0RB201001_予兆検知.md" in s
    assert f"{PJ}/01_設計案/0RB202001_A案.md" in s
    assert f"{PJ}/01_設計案/0RB203001_B案.md" in s


# ---------- v0.67: 個人 vault も共有と同じ並び(90_共有 はなし) ----------

def test_own_note_is_moved_to_its_place(cloud):
    """F-57: 振り分け先と違うフォルダにある自分のノートは、共有と同じ場所へ移す。"""
    yu = cloud["yu"].personal
    write(yu / "03_イシュー/0RB010001_そり.md",
          f"---\nid: 0RB010001\ntype: イシュー\nproject: [{PJ}]\n---\n")
    write(yu / "00_inbox/0RB011001_親なし.md", "---\nid: 0RB011001\ntype: タスク\n---\n")  # inbox は触らない
    write(yu / "04_タスク/0RB012001_測る.md", f"---\nid: 0RB012001\ntype: タスク\nproject: [{PJ}]\n---\n")
    run_once(cloud["yu"])
    assert (yu / f"{PJ}/03_イシュー/0RB010001_そり.md").exists()
    assert not (yu / "03_イシュー/0RB010001_そり.md").exists()
    assert (yu / f"{PJ}/04_タスク/0RB012001_測る.md").exists()    # 親がなくても project で決まる
    assert not (yu / "04_タスク").exists()                         # 空になった一番上のフォルダは片付ける
    assert (yu / "00_inbox/0RB011001_親なし.md").exists()
    assert (yu / "03_イシュー/0RB006001_迷子.md").exists()        # 台帳のないプロジェクトは動かさない
    assert "置き場所を直した: 03_イシュー/0RB010001_そり.md" in report(cloud["yu"])
    assert f"{PJ}/03_イシュー/0RB010001_そり.md" in files(cloud["shared"])


def test_note_without_author_from_shared_is_not_taken(cloud):
    """共有 vault で直接作った author のないノート(台帳など)は、配られても自分のものにしない。"""
    for _ in range(2):
        run_once(cloud["yu"])
    ledger = cloud["yu"].personal / f"{PJ}/0RA00A001_{PJ}.md"
    assert "author" not in text(ledger)
    assert "author" not in text(cloud["shared"] / f"{PJ}/0RA00A001_{PJ}.md")
    assert "競合" not in report(cloud["yu"]).split("## 記録")[0].replace("(なし)", "")


def test_old_shared_folder_stops_sync(cloud):
    (cloud["yu"].personal / "90_共有").mkdir()
    run_once(cloud["yu"])
    assert "90_共有/ が残っているので、同期を止めています" in report(cloud["yu"])
    assert not (cloud["shared"] / "共通/02_ノード/0RB001001_水.md").exists()
