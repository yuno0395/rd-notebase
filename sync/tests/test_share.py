"""集約と再配布(F-05〜11、F-14、F-15)。山田 と 田中 の2人分の vault で確かめる。"""

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
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv", "名前,記号,使い始めた日\n山田,001,2026-10-24\n田中,002,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md", "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [山田, 田中]\n---\n")
    write(shared / "別PJ/0RA00B001_別PJ.md", "---\nid: 0RA00B001\ntype: プロジェクト\nmembers: [山田]\n---\n")
    write(shared / "別PJ/03_イシュー/0RA00C001_別の話.md",
          "---\nid: 0RA00C001\nauthor: 山田\ntype: イシュー\nproject: [別PJ]\n---\n")

    yu = root / "個人_山田"
    write(yu / "_仕組み/個人設定.md", '---\nname: 山田\n---\n')
    write(yu / "共通/02_ノード/0RB001001_水.md", "---\nid: 0RB001001\ntype: ノード\n---\n水の話\n")
    write(yu / f"{PJ}/03_イシュー/0RB002001_ヒケ.md",
          f"---\nid: 0RB002001\ntype: イシュー\nimpact: 出荷\nproject: [{PJ}]\n---\n[[0RB001001_水|水]] が原因\n")
    write(yu / f"{PJ}/04_タスク/0RB003001_保圧を変える.md",
          '---\nid: 0RB003001\ntype: タスク\nparent: ["[[0RB002001_ヒケ|ヒケ]]"]\n---\n')
    write(yu / "_仕組み/attachments/0RB003001/図.excalidraw.md", "図のデータ\n")
    write(yu / "共通/02_ノード/0RB004001_秘密のメモ.md", "---\nid: 0RB004001\ntype: ノード\nvisibility: 個人\n---\n")
    write(yu / "00_日誌/メモ/2026-10-29 思いつき.md", MEMO)
    write(yu / "00_日誌/メモ/0RB008001_考え中.md", MEMO_ID)       # v0.85 からメモにも id
    # 「このメモを〜にする」でタスクにしたメモ(同じ id のまま、プロジェクトのフォルダへ)
    write(yu / f"{PJ}/04_タスク/0RB009001_吸水を測る.md",
          f'---\nid: 0RB009001\ntype: タスク\nauthor: [山田]\naliases: ["吸水を測る"]\nproject: [{PJ}]\n---\nPA66 の吸水\n')
    write(yu / f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md",
          '---\nid: 0RB005001\ntype: ナレッジ\nparent: ["[[0RB003001_保圧を変える|保圧を変える]]"]\n'
          'risk_reduction:\n  - "[[0RB002001_ヒケ]] 出荷→小"\nusefulness: B\n---\n')
    write(yu / "03_イシュー/0RB006001_迷子.md", "---\nid: 0RB006001\ntype: イシュー\nproject: [無いPJ]\n---\n")
    write(yu / "共通/02_ノード/0RB007001_顧客の寸法.md",
          "---\nid: 0RB007001\ntype: ノード\n---\n[[0RC001001_顧客図面]] を見た\n")

    kato = root / "個人_田中"
    write(kato / "_仕組み/個人設定.md", '---\nname: 田中\n---\n')
    write(kato / "共通/02_ノード/0RB101002_鉄.md", "---\nid: 0RB101002\ntype: ノード\n---\n")

    secret = root / "機密_顧客A"
    (secret / "_仕組み").mkdir(parents=True)
    write(secret / "06_事実/0RC001001_顧客図面.md", "---\nid: 0RC001001\n---\n")

    def cfg(member):
        c = Config(member=member, personal=root / f"個人_{member}", shared=shared,
                   secret=[secret], backup_dir=tmp_path / f"backup_{member}",
                   state_dir=tmp_path / f"state_{member}", idle_seconds=0)
        c.code = member_code(c)
        return c

    return {"root": root, "shared": shared, "yu": cfg("山田"), "kato": cfg("田中")}


MEMO = "---\ntype: メモ\nvisibility: 個人\n---\n[[0RB001001_水|水]] を温めたら?\n"
MEMO_ID = '---\nid: 0RB008001\ntype: メモ\nauthor: [山田]\naliases: ["考え中"]\nvisibility: 個人\n---\nまだ見せない\n'


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
    assert "author: 山田" in text(cloud["shared"] / "共通/02_ノード/0RB001001_水.md")


def test_does_not_collect_when_conditions_fail(cloud):
    run_once(cloud["yu"])
    s = " ".join(files(cloud["shared"]))
    r = report(cloud["yu"])
    todo = r.split("## 警告")[0]
    assert "秘密のメモ" not in s and "秘密のメモ" not in todo     # visibility 個人は知らせもしない
    assert "思いつき" not in s and "思いつき" not in r                 # 共有しないメモ(00_日誌/メモ/)
    assert text(cloud["yu"].personal / "00_日誌/メモ/2026-10-29 思いつき.md") == MEMO  # id もつけない
    assert "考え中" not in s and "考え中" not in r                     # id のあるメモも集めない
    assert text(cloud["yu"].personal / "00_日誌/メモ/0RB008001_考え中.md") == MEMO_ID
    assert f"{PJ}/04_タスク/0RB009001_吸水を測る.md" in files(cloud["shared"])  # メモから変えたものは集める
    assert "保圧のナレッジ" not in s
    assert "保圧のナレッジ|保圧のナレッジ]] の reviewed_by が空です" in r
    assert "迷子" not in s and "プロジェクト「無いPJ」の台帳が共有 vault にありません" in r
    assert "顧客の寸法" not in s and "機密へのリンク" in r          # F-40


def test_knowledge_of_big_issue_needs_another_reviewer(cloud):
    k = cloud["yu"].personal / f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md"
    write(k, text(k).replace("usefulness: B", "usefulness: B\nreviewed_by: [山田]"))
    run_once(cloud["yu"])
    assert "確認待ち" in report(cloud["yu"])
    write(k, text(k).replace("reviewed_by: [山田]", "reviewed_by: [山田, 田中]"))
    run_once(cloud["yu"])
    assert f"{PJ}/05_ナレッジ/0RB005001_保圧のナレッジ.md" in files(cloud["shared"])


def test_redistributes_to_members_only(cloud):
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    got = files(cloud["kato"].personal)                            # 共有と同じ場所に配る
    assert "共通/02_ノード/0RB001001_水.md" in got
    assert f"{PJ}/04_タスク/0RB003001_保圧を変える.md" in got
    assert f"{PJ}/0RA00A001_{PJ}.md" in got
    assert not any(x.startswith("別PJ/") for x in got)            # 田中は 別PJ のメンバーでない
    assert (cloud["kato"].personal / "_仕組み/attachments/0RB003001/図.excalidraw.md").exists()
    # 自分が書いたノートは配らない(F-10)
    run_once(cloud["yu"])
    assert [x for x in files(cloud["yu"].personal) if "0RB001001" in x] == ["共通/02_ノード/0RB001001_水.md"]
    assert "共通/02_ノード/0RB101002_鉄.md" in files(cloud["yu"].personal)
    assert not (cloud["yu"].personal / "90_共有").exists()


def test_own_ledger_made_in_shared_comes_to_personal(cloud):
    """共有 vault で作った自分の台帳は、個人 vault に一度だけ取り込む(Ctrl+N の選択肢に出すため)。ほかの自分のノートは取り込まない。"""
    shared = cloud["shared"]
    write(shared / "新PJ/0RA00D001_新PJ.md", "---\nid: 0RA00D001\ntype: プロジェクト\nauthor: [山田]\nmembers: [山田]\n---\n")
    write(shared / "新PJ/03_イシュー/0RA00E001_共有で書いた.md",
          "---\nid: 0RA00E001\ntype: イシュー\nauthor: [山田]\nproject: [新PJ]\n---\n")
    run_once(cloud["yu"])
    yu = cloud["yu"].personal
    assert text(yu / "新PJ/0RA00D001_新PJ.md") == text(shared / "新PJ/0RA00D001_新PJ.md")
    assert not (yu / "新PJ/03_イシュー/0RA00E001_共有で書いた.md").exists()
    # 取り込んだあとは自分のノート。手元で消したら戻さない
    (yu / "新PJ/0RA00D001_新PJ.md").unlink()
    run_once(cloud["yu"])
    assert not (yu / "新PJ/0RA00D001_新PJ.md").exists()


def test_second_run_changes_nothing(cloud):
    for _ in range(2):
        run_once(cloud["yu"])
        run_once(cloud["kato"])
    before = {p: text(cloud["root"] / p) for p in files(cloud["root"])}
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    after = {p: text(cloud["root"] / p) for p in files(cloud["root"]) if not p.endswith("_仕組み/同期レポート.md")}
    assert after == {p: v for p, v in before.items() if not p.endswith("_仕組み/同期レポート.md")}


def test_update_flows_through(cloud):
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    water = cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md"
    write(water, text(water) + "0℃で凍る\n")
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    copy = cloud["kato"].personal / "共通/02_ノード/0RB001001_水.md"
    assert "0℃で凍る" in text(copy)


def test_adopted_note_comes_back_to_author(cloud):
    """田中が配られたノートの author に自分を足して書き足すと、共有を経て 山田 のノートに入る。"""
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    dest = cloud["kato"].personal / "共通/02_ノード/0RB001001_水.md"
    write(dest, text(dest).replace("author: 山田", 'author: ["山田", "田中"]') + "田中の書き足し\n")
    run_once(cloud["kato"])
    assert "田中の書き足し" in text(cloud["shared"] / "共通/02_ノード/0RB001001_水.md")
    run_once(cloud["yu"])
    assert "田中の書き足し" in text(cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md")
    assert "取り込み" in report(cloud["yu"])
    assert 'author: ["山田", "田中"]' in text(cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md")


def test_conflict_keeps_both_and_resolves(cloud):
    run_once(cloud["yu"])
    shared_water = cloud["shared"] / "共通/02_ノード/0RB001001_水.md"
    write(shared_water, text(shared_water) + "共有で直接の書き足し\n")
    water = cloud["yu"].personal / "共通/02_ノード/0RB001001_水.md"
    write(water, text(water) + "山田 の書き足し\n")
    run_once(cloud["yu"])
    conflicts = [p for p in shared_water.parent.iterdir() if "_競合_山田_" in p.name]
    assert len(conflicts) == 1 and "山田 の書き足し" in text(conflicts[0])
    assert "共有で直接の書き足し" in text(shared_water)               # 上書きしない
    assert "山田 の書き足し" not in text(shared_water)
    assert "競合: 共有/共通/02_ノード/0RB001001_水.md" in report(cloud["yu"])
    # 次の回も競合ファイルを増やさない
    run_once(cloud["yu"])
    assert len([p for p in shared_water.parent.iterdir() if "_競合_" in p.name]) == 1
    # 共有側でまとめると、個人に入って競合が消える
    write(shared_water, text(shared_water) + "山田 の書き足し\n")
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
    run_once(cloud["kato"])
    assert not any("_競合_" in x for x in files(cloud["kato"].personal))


def test_editing_others_note_is_put_back(cloud):
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    copy = cloud["kato"].personal / "共通/02_ノード/0RB001001_水.md"
    write(copy, text(copy) + "ここに書いてしまった\n")
    run_once(cloud["kato"])
    assert "他の人のノート: 共通/02_ノード/0RB001001_水.md が手元で変わっていた" in report(cloud["kato"])
    assert "ここに書いてしまった" not in text(cloud["shared"] / "共通/02_ノード/0RB001001_水.md")
    assert "ここに書いてしまった" not in text(copy)                 # 共有の中身に戻す
    assert list((cloud["kato"].personal.parent.parent / "backup_田中").rglob("0RB001001_水.md"))


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
          "---\nid: 0RB001001\nauthor: 田中\ntype: ノード\n---\n")
    run_once(cloud["yu"])
    assert "0RB001001_水.md" not in " ".join(files(cloud["shared"]))
    assert "同じ id: 0RB001001" in report(cloud["yu"])


def test_dry_run_writes_only_report(cloud):
    before = files(cloud["root"])
    run_once(cloud["yu"], dry_run=True)
    after = files(cloud["root"])
    assert after - before == {"個人_山田/_仕組み/同期レポート.md"}
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
    """田中の「蒸留水」(別名 H2O)が共有にあり、山田 が別に「H2O」を作った。"""
    kato = cloud["kato"].personal
    write(kato / "共通/02_ノード/0RB102002_蒸留水.md",
          "---\nid: 0RB102002\ntype: ノード\naliases:\n  - 蒸留水\n  - H2O\n---\n## これは何か\n田中のメモ\n")
    run_once(cloud["kato"])
    yu = cloud["yu"].personal
    write(yu / "共通/02_ノード/0RB008001_H2O.md",
          "---\nid: 0RB008001\ntype: ノード\naliases: [H2O, 純水]\n---\n## これは何か\n"
          "山田のメモ ![[写真.png]]\n## 何に影響するか\n")
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
    assert "- [ ] 同じもの: [[0RB008001_H2O|H2O]] を [[0RB102002_蒸留水|蒸留水]](田中) にまとめる" in r
    assert "- [ ] 別もの: [[0RB008001_H2O|H2O]] と [[0RB102002_蒸留水|蒸留水]](田中)" in r
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
    assert 'author: ["田中", "山田"]' in water
    assert "## まとめたメモ(H2O、山田、" in water
    assert "- [ ] 山田: 「H2O」のメモを上の本文に書き直して、この章を消す 📅 " in water
    assert "### これは何か\n山田のメモ" in water and "何に影響するか" not in water
    assert (shared / "_仕組み/attachments/0RB102002/写真.png").exists()
    # 自分のノードは archive へ、リンクは付け替え
    assert not (yu / "共通/02_ノード/0RB008001_H2O.md").exists()
    assert 'merged_into: "[[0RB102002_蒸留水|蒸留水]]"' in text(yu / "99_archive/0RB008001_H2O.md")
    issue = text(yu / f"{PJ}/03_イシュー/0RB009001_濁り.md")
    assert "[[0RB102002_蒸留水|H2O]] と [[0RB102002_蒸留水|H2O]]" in issue
    assert "同じもの:" not in report(cloud["yu"])
    # 山田 も author に入ったが、最初に書いたのは田中なので 山田 にも配られる。田中の手元にも入る
    run_once(cloud["yu"])
    assert "## まとめたメモ" in text(yu / "共通/02_ノード/0RB102002_蒸留水.md")
    run_once(cloud["kato"])
    assert "## まとめたメモ" in text(cloud["kato"].personal / "共通/02_ノード/0RB102002_蒸留水.md")
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
    # 行き先の決まらないものは、一番上の種類のフォルダから 00_inbox/ へ移す(v0.72)
    assert (yu / "00_inbox/0RB006001_迷子.md").exists()
    assert not (yu / "03_イシュー").exists()
    assert "置き場所を直した: 03_イシュー/0RB010001_そり.md" in report(cloud["yu"])
    assert f"{PJ}/03_イシュー/0RB010001_そり.md" in files(cloud["shared"])


def test_inbox_note_moves_when_project_is_written(cloud):
    """F-57(v0.72): 00_inbox/ のノートに project か parent を書けば、そのプロジェクトのフォルダへ移り、次の同期で集まる。"""
    yu = cloud["yu"].personal
    note = write(yu / "00_inbox/0RB013001_あとで決める.md", "---\nid: 0RB013001\ntype: イシュー\nproject: []\n---\n")
    run_once(cloud["yu"])
    assert note.exists()                                            # 決まるまでは inbox に置いたまま
    assert not any("0RB013001" in x for x in files(cloud["shared"]))
    write(note, f"---\nid: 0RB013001\ntype: イシュー\nproject: [{PJ}]\n---\n")
    write(yu / "00_inbox/0RB014001_記録.md",
          '---\nid: 0RB014001\ntype: 議事録\nparent: ["[[0RB002001_ヒケ|ヒケ]]"]\n---\n')
    run_once(cloud["yu"])
    moved = yu / f"{PJ}/03_イシュー/0RB013001_あとで決める.md"
    assert moved.exists() and not note.exists()
    assert (yu / f"{PJ}/04_タスク/0RB014001_記録.md").exists()      # 議事録はタスクのフォルダへ
    run_once(cloud["yu"])
    assert "author:" in text(moved)
    assert f"{PJ}/03_イシュー/0RB013001_あとで決める.md" in files(cloud["shared"])


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


def test_parts_nodes_go_to_common_nodes(cloud):
    """部品(type: ノード、kind: 部品)で project のないものは、ノードと同じく 共通/02_ノード/ へ集める。
    プロジェクトのフォルダに置いても移す(Assy の project は継がない)。"""
    yu = cloud["yu"].personal
    write(yu / "共通/02_ノード/0RB301001_ポンプAssy.md",
          "---\nid: 0RB301001\ntype: ノード\nkind: 部品\nvalue_kind: 組み立て\nparent: []\n個数: 1\nstatus: 未発注\n---\n")
    write(yu / f"{PJ}/0RB302001_モーター.md",
          "---\nid: 0RB302001\ntype: ノード\nkind: 部品\nvalue_kind: 組み立て\nparent: [\"[[0RB301001_ポンプAssy|ポンプAssy]]\"]\n"
          "project: []\n単価: 1200\n個数: 2\n発注先: 試し商会\nstatus: 発注済\nPurchaseNo: P-001\n---\n")
    run_once(cloud["yu"])
    s = files(cloud["shared"])
    assert "共通/02_ノード/0RB301001_ポンプAssy.md" in s
    assert "共通/02_ノード/0RB302001_モーター.md" in s
    assert "PurchaseNo: P-001" in text(cloud["shared"] / "共通/02_ノード/0RB302001_モーター.md")


def test_project_parts_go_to_project_nodes(cloud):
    """v0.76: project を1つ書いた部品は <プロジェクト>/02_ノード/ に置く。共通/02_ノード/ にあれば移す(古い置き場所も読む)。
    project が2つ以上か 共通 なら 共通/02_ノード/。ふつうのノードは project を書いても 共通。"""
    yu = cloud["yu"].personal
    pump = write(yu / "共通/02_ノード/0RB303001_ポンプAssy.md",
                 f"---\nid: 0RB303001\ntype: ノード\nkind: 部品\nproject: [{PJ}]\nparent: []\n---\n")
    write(yu / "共通/02_ノード/0RB304001_ボルト.md",
          f"---\nid: 0RB304001\ntype: ノード\nkind: 部品\nproject: [{PJ}, 別PJ]\n---\n")
    write(yu / "共通/02_ノード/0RB305001_ふつうのノード.md",
          f"---\nid: 0RB305001\ntype: ノード\nproject: [{PJ}]\n---\n")
    run_once(cloud["yu"])
    moved = yu / f"{PJ}/02_ノード/0RB303001_ポンプAssy.md"
    assert moved.exists() and not pump.exists()
    s = files(cloud["shared"])
    assert f"{PJ}/02_ノード/0RB303001_ポンプAssy.md" in s
    assert "共通/02_ノード/0RB304001_ボルト.md" in s
    assert "共通/02_ノード/0RB305001_ふつうのノード.md" in s
    # 部品を親にするタスクは、部品のプロジェクトのフォルダへ
    write(yu / "04_タスク/0RB306001_見積を取る.md",
          '---\nid: 0RB306001\ntype: タスク\nparent: ["[[0RB303001_ポンプAssy|ポンプAssy]]"]\n---\n')
    # project を消せば 共通/02_ノード/ へ戻り、共有のファイルも移る
    write(moved, text(moved).replace(f"project: [{PJ}]", "project: []"))
    run_once(cloud["yu"])
    assert (yu / "共通/02_ノード/0RB303001_ポンプAssy.md").exists()
    s = files(cloud["shared"])
    assert "共通/02_ノード/0RB303001_ポンプAssy.md" in s
    assert f"{PJ}/02_ノード/0RB303001_ポンプAssy.md" not in s


def test_project_parts_reach_only_project_members(cloud):
    """プロジェクトの部品は、ほかのプロジェクトのノートと同じく、そのプロジェクトのメンバーにだけ配る。"""
    write(cloud["yu"].personal / "別PJ/02_ノード/0RB307001_別PJの部品.md",
          "---\nid: 0RB307001\ntype: ノード\nkind: 部品\nproject: [別PJ]\n---\n")
    write(cloud["yu"].personal / f"{PJ}/02_ノード/0RB308001_試しPJの部品.md",
          f"---\nid: 0RB308001\ntype: ノード\nkind: 部品\nproject: [{PJ}]\n---\n")
    run_once(cloud["yu"])
    run_once(cloud["kato"])
    got = files(cloud["kato"].personal)
    assert f"{PJ}/02_ノード/0RB308001_試しPJの部品.md" in got
    assert not any("0RB307001" in x for x in got)


def test_author_candidates_follow_project_members(cloud):
    """選択肢.md の author に、プロジェクトの台帳の members が箇条書きで入る(F-58)。status はそのまま。"""
    body = "---\n# 候補\nstatus:\n  - 未着手\n  - 完了\nauthor: []\n---\n"
    for root in (cloud["shared"], cloud["yu"].personal):
        write(root / "_仕組み/templates/選択肢.md", body)
    run_once(cloud["yu"])
    for root in (cloud["shared"], cloud["yu"].personal):
        got = text(root / "_仕組み/templates/選択肢.md")
        assert "status:\n  - 未着手\n  - 完了\n" in got
        assert "author:\n  - 山田\n  - 田中\n---\n" in got
    before = text(cloud["shared"] / "_仕組み/templates/選択肢.md")
    run_once(cloud["yu"])
    assert text(cloud["shared"] / "_仕組み/templates/選択肢.md") == before


# ---------- visibility: PIP・Internal use only・プロジェクト名・EXT(v0.91) ----------

def test_new_visibility_values_are_checked(cloud):
    yu, shared = cloud["yu"], cloud["shared"]
    write(shared / "_仕組み/EXT_一覧.csv", "名前,社内の担当\nEXT_協力工場A,山田\n")
    good = {"0RB201001": f"[{PJ}, EXT_協力工場A]", "0RB202001": "[Internal use only]", "0RB203001": f"[{PJ}, 別PJ]"}
    bad = {"0RB204001": "[チーム外秘]", "0RB205001": f"[Internal use only, {PJ}]",
           "0RB206001": "[PIP, EXT_協力工場A]", "0RB207001": f"[{PJ}, EXT_知らない]"}
    for nid, v in {**good, **bad}.items():
        write(yu.personal / f"{PJ}/03_イシュー/{nid}_話{nid}.md",
              f"---\nid: {nid}\ntype: イシュー\nproject: [{PJ}]\nvisibility: {v}\n---\n")
    run_once(yu)
    got = files(shared)
    for nid in good:
        assert f"{PJ}/03_イシュー/{nid}_話{nid}.md" in got, nid
    for nid in bad:
        assert f"{PJ}/03_イシュー/{nid}_話{nid}.md" not in got, nid
    r = report(yu)
    assert "「チーム外秘」は決まった言葉でも台帳のプロジェクト名でもありません" in r
    assert "Internal use only とプロジェクト名は一緒に書けません" in r
    assert (yu.personal / "00_PIP/メモ/0RB206001_話0RB206001.md").exists()   # PIP が入っていれば、安全のため PIP として扱う
    assert "「EXT_知らない」は EXT_一覧.csv に登録されていません" in r
    # 作るときの窓が社外の相手を出せるよう、一覧を個人 vault に写す
    assert text(yu.personal / "_仕組み/EXT_一覧.csv") == "名前,社内の担当\nEXT_協力工場A,山田\n"


def test_pip_note_moves_to_pip_folder_and_is_not_shared(cloud):
    yu, shared = cloud["yu"], cloud["shared"]
    write(yu.personal / f"{PJ}/03_イシュー/0RB211001_見込み.md",
          f"---\nid: 0RB211001\ntype: イシュー\nproject: [{PJ}]\nvisibility: [PIP]\n---\n")
    write(yu.personal / "00_PIP/メモ/0RB212001_下書き.md", "---\nid: 0RB212001\ntype: イシュー\nvisibility: [Internal use only]\n---\n")
    run_once(yu)
    assert (yu.personal / "00_PIP/メモ/0RB211001_見込み.md").exists()
    assert not (yu.personal / f"{PJ}/03_イシュー/0RB211001_見込み.md").exists()
    got = " ".join(files(shared))
    assert "0RB211001" not in got
    assert "0RB212001" not in got   # 00_PIP/ の中は、visibility を書き換えても読まない(「共有する」で移す)


def test_weekly_follows_visibility(cloud):
    yu, shared = cloud["yu"], cloud["shared"]
    write(yu.personal / "00_週報/2026-W45.md", "---\ntype: 週報\nvisibility: [Internal use only]\n---\n今週\n")
    write(yu.personal / "00_週報/2026-W44.md", "---\ntype: 週報\nvisibility: [PIP]\n---\n内緒\n")
    write(yu.personal / "00_週報/2026-W43.md", "---\ntype: 週報\nvisibility: [無いPJ]\n---\n")
    write(yu.personal / "00_PIP/週報/2026-W42.md", "---\ntype: 週報\nvisibility: [Internal use only]\n---\n")
    run_once(yu)
    assert text(shared / "00_週報/山田/2026-W45.md").endswith("今週\n")
    assert not (shared / "00_週報/山田/2026-W44.md").exists()
    assert not (shared / "00_週報/山田/2026-W43.md").exists()
    assert not (shared / "00_週報/山田/2026-W42.md").exists()   # 00_PIP/ は絶対に写さない
    assert "週報 00_週報/2026-W43.md の visibility が決まりに合いません" in report(yu)


def test_node_for_one_project_goes_to_project_folder(cloud):
    """見せる範囲がプロジェクト1つだけのノードは <PJ>/02_ノード/ に置く。"""
    yu, shared = cloud["yu"], cloud["shared"]
    write(yu.personal / "共通/02_ノード/0RB221001_試しの寸法.md",
          f"---\nid: 0RB221001\ntype: ノード\nvisibility: [{PJ}]\n---\n")
    write(yu.personal / "共通/02_ノード/0RB222001_両方の寸法.md",
          f"---\nid: 0RB222001\ntype: ノード\nvisibility: [{PJ}, 別PJ]\n---\n")
    write(yu.personal / "共通/02_ノード/0RB223001_社内の寸法.md",
          "---\nid: 0RB223001\ntype: ノード\nvisibility: [Internal use only]\n---\n")
    run_once(yu)
    got = files(shared)
    assert f"{PJ}/02_ノード/0RB221001_試しの寸法.md" in got
    assert (yu.personal / f"{PJ}/02_ノード/0RB221001_試しの寸法.md").exists()   # 手元も同じ場所へ移す(F-57)
    assert "共通/02_ノード/0RB222001_両方の寸法.md" in got                      # 2つ以上は 共通
    assert "共通/02_ノード/0RB223001_社内の寸法.md" in got
