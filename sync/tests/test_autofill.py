"""おまけの自動入力(F-26・F-27・F-31)と、Box の競合の複製(F-16)。"""

from datetime import datetime
from pathlib import Path

import pytest

from notesync import ids
from notesync.config import Config, member_code
from notesync.run import run_once

from .conftest import text

PJ = "試しPJ"
NOW = datetime(2026, 10, 24, 9, 0, tzinfo=ids.JST).timestamp()


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(body)
    return path


def issue(yu: Path, nid: str, name: str, extra: str = "") -> Path:
    return write(yu / f"03_イシュー/{nid}_{name}.md",
                 f"---\nid: {nid}\nauthor: Yu\ntype: イシュー\nproject: [{PJ}]\n{extra}---\n## リスク\n")


@pytest.fixture
def box(tmp_path):
    root = tmp_path / "Box"
    shared = root / "共有"
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv", "名前,記号,使い始めた日\nYu,001,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md",
          "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [Yu]\n---\n"
          "## 期間・主な節目\n節目ごとに1行\n| 節目 | 計画日 | 見込み日 |\n| --- | --- | --- |\n"
          "| DR1 | 2026-11-07 | 2026-11-14 |\n| 量産開始 | 2027-04-01 | 2027-04-01 |\n")
    yu = root / "個人_Yu"
    write(yu / "_仕組み/記録/私.yaml", 'name: Yu\ncode: "001"\n')
    c = Config(member="Yu", personal=yu, shared=shared, backup_dir=tmp_path / "backup",
               state_dir=tmp_path / "state", idle_seconds=0)
    c.code = member_code(c)
    return c


def report(c) -> str:
    return text(c.personal / "_仕組み/同期レポート.md")


@pytest.mark.parametrize("impact,speed,want", [
    ("方針", "すぐ", 1), ("絞込", "すぐ", 1), ("方針", "時間がかかる", 2), ("絞込", "時間がかかる", 2),
    ("出荷", "すぐ", 2), ("未判定", "すぐ", 2), ("出荷", "時間がかかる", 3), ("中", "すぐ", 3),
    ("中", "時間がかかる", 4), ("小", "すぐ", 4),
])
def test_priority_table(box, impact, speed, want):
    p = issue(box.personal, "0RB001001", "ヒケ", f"impact: {impact}\nspeed: {speed}\n")
    run_once(box, now=NOW)
    assert f"priority: {want}" in text(p)


def test_priority_keeps_other_lines_and_updates(box):
    p = issue(box.personal, "0RB001001", "ヒケ", "impact: 出荷   # 迷ったら出荷\nspeed: すぐ\npriority: 4\n")
    run_once(box, now=NOW)
    t = text(p)
    assert "priority: 2" in t and "priority: 4" not in t
    assert "impact: 出荷   # 迷ったら出荷" in t
    # 共有にも同じ同期で届く
    assert "priority: 2" in text(box.shared / f"{PJ}/03_イシュー/0RB001001_ヒケ.md")


def test_old_big_impact_is_shipping_and_reported(box):
    p = issue(box.personal, "0RB001001", "ヒケ", "impact: 大\nspeed: 時間がかかる\n")
    run_once(box, now=NOW)
    assert "priority: 3" in text(p)
    assert "impact「大」は v0.22 までの書き方です" in report(box)


def test_lead_weeks_raises_to_1(box):
    # 次のマイルストーン DR1 の見込み 2026-11-14 まで 3 週。4 週かかるので priority 1
    near = issue(box.personal, "0RB001001", "認証", "impact: 出荷\nspeed: 時間がかかる\nlead_weeks: 4\n")
    far = issue(box.personal, "0RB002001", "金型", "impact: 出荷\nspeed: 時間がかかる\nlead_weeks: 2\n")
    run_once(box, now=NOW)
    assert "priority: 1" in text(near)
    assert "priority: 3" in text(far)


def test_lead_weeks_uses_named_milestone(box):
    p = issue(box.personal, "0RB003001", "長納期部品",
              "impact: 中\nspeed: 時間がかかる\nlead_weeks: 30\nmilestone: 量産開始\n")
    run_once(box, now=NOW)
    assert "priority: 1" in text(p)
    assert "期限から逆算して priority 1 にした" in report(box)


def test_lead_weeks_reads_old_milestones_property(box):
    # v0.48 までの属性 milestones: [{name, plan, forecast}] も読み続ける
    write(box.shared / f"{PJ}/0RA00A001_{PJ}.md",
          "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [Yu]\nmilestones:\n"
          "  - {name: DR1, plan: 2026-11-07, forecast: 2026-11-14}\n---\n")
    p = issue(box.personal, "0RB001001", "認証", "impact: 出荷\nspeed: 時間がかかる\nlead_weeks: 4\n")
    run_once(box, now=NOW)
    assert "priority: 1" in text(p)


def test_previous_and_generation(box):
    yu = box.personal
    issue(yu, "0RB001001", "ヒケ", "impact: 出荷\nspeed: すぐ\n")
    write(yu / "04_タスク/0RB002001_リブを足す.md",
          '---\nid: 0RB002001\nauthor: Yu\ntype: タスク\nparent: ["[[0RB001001_ヒケ|ヒケ]]"]\n---\n'
          "## リスクはどう変わったか\n- [[0RB003001_そり|そり]] が出るかも\n## 次\n[[0RB004001_無関係]]\n")
    child = issue(yu, "0RB003001", "そり", "impact: 出荷\nspeed: すぐ\n")
    other = issue(yu, "0RB004001", "無関係", "impact: 出荷\nspeed: すぐ\n")
    run_once(box, now=NOW)
    t = text(child)
    assert 'previous: ["[[0RB002001_リブを足す|リブを足す]]"]' in t
    assert "generation: 2" in t
    assert "previous" not in text(other)                 # リスクの欄の外のリンクは見ない
    assert "generation" not in text(yu / "03_イシュー/0RB001001_ヒケ.md")  # 元のイシューには書かない
    assert "previous を補った: [[0RB003001_そり|そり]]" in report(box)


def test_generation_mismatch_and_loop(box):
    yu = box.personal
    issue(yu, "0RB001001", "A", 'impact: 出荷\nspeed: すぐ\nprevious: ["[[0RB002001_B]]"]\n')
    issue(yu, "0RB002001", "B", 'impact: 出荷\nspeed: すぐ\nprevious: ["[[0RB001001_A]]"]\n')
    issue(yu, "0RB003001", "C", "impact: 出荷\nspeed: すぐ\n")
    issue(yu, "0RB004001", "D", 'impact: 出荷\nspeed: すぐ\nprevious: ["[[0RB003001_C]]"]\ngeneration: 5\n')
    run_once(box, now=NOW)
    r = report(box)
    assert "previous が輪になっています" in r
    assert "generation の食い違い: [[0RB004001_D|D]] は 5 ですが、previous をたどると 2 です" in r


def test_dry_run_writes_nothing(box):
    p = issue(box.personal, "0RB001001", "ヒケ", "impact: 方針\nspeed: すぐ\n")
    before = text(p)
    run_once(box, dry_run=True, now=NOW)
    assert text(p) == before
    assert "予定: priority を 1 にした" in report(box)


def test_box_conflict_copies(box):
    yu = box.personal
    issue(yu, "0RB001001", "ヒケ", "impact: 出荷\nspeed: すぐ\n")
    write(yu / "03_イシュー/0RB001001_ヒケ (Yu's conflicted copy 2026-10-24).md", "x")
    write(yu / "00_日誌/デイリー/2026-10-24 (1).md", "x")
    write(yu / "00_日誌/デイリー/2026-10-24.md", "x")
    write(yu / "02_ノード/部品 (2).md", "元がないので数えない")
    write(box.shared / f"{PJ}/03_イシュー/メモ (競合 Yu).md", "x")
    run_once(box, now=NOW)
    r = report(box)
    assert "Box の競合の複製: 個人/03_イシュー/0RB001001_ヒケ (Yu's conflicted copy 2026-10-24).md があります。" \
           "個人/03_イシュー/0RB001001_ヒケ.md と見比べて" in r
    assert "Box の競合の複製: 個人/00_日誌/デイリー/2026-10-24 (1).md" in r
    assert "Box の競合の複製: 個人/02_ノード" not in r      # 元がない番号つきは複製と見なさない
    assert "Box の競合の複製: 共有/試しPJ/03_イシュー/メモ (競合 Yu).md があります。中身を確かめて" in r
    # 複製には id をつけず、共有にも集めない
    assert not list(box.shared.rglob("*conflicted*"))


def test_note_history(box):
    from notesync.history import done_date, extensions, first_due, history_path, read_rows
    yu = box.personal
    task = write(yu / "04_タスク/0RB002001_試作.md",
                 "---\nid: 0RB002001\nauthor: Yu\ntype: タスク\nstatus: 進行中\ndue: 2026-10-30\n---\n")
    run_once(box, now=NOW)
    t = text(task)
    write(task, t.replace("due: 2026-10-30", "due: 2026-11-06"))
    run_once(box, now=NOW + 86400)
    write(task, text(task).replace("status: 進行中", "status: 完了"))
    run_once(box, now=NOW + 2 * 86400)
    run_once(box, now=NOW + 3 * 86400)              # 変わらなければ足さない
    rows = read_rows(history_path(box.shared, "Yu"))
    assert [(r["項目"], r["前"], r["後"]) for r in rows] == [
        ("due", "", "2026-10-30"), ("status", "", "進行中"),
        ("due", "2026-10-30", "2026-11-06"), ("status", "進行中", "完了")]
    assert first_due(rows, "0RB002001") == "2026-10-30"
    assert extensions(rows, "0RB002001") == 1
    assert done_date(rows, "0RB002001") == "2026-10-26"
    assert "due" in text(task) and "first" not in text(task)   # ノートには書かない
    assert history_path(box.shared, "Yu").read_bytes().startswith(b"\xef\xbb\xbf")  # Excel 用の BOM は先頭だけ
    assert history_path(box.shared, "Yu").read_bytes().count(b"\xef\xbb\xbf") == 1


def test_daily_note_notice(box):
    from notesync.daily import TITLE
    yu = box.personal
    daily = write(yu / "00_日誌/デイリー/2026-10-24.md", "# 2026-10-24\n\n## タイムライン\n- [ ] 09:00 打ち合わせ\n")
    write(yu / "05_ナレッジ/0RB005001_保圧.md", "---\nid: 0RB005001\nauthor: Yu\ntype: ナレッジ\n---\n")
    run_once(box, now=NOW)
    t = text(daily)
    assert t.startswith(f"# 2026-10-24\n\n{TITLE}\n> - 共有されていない: 未入力: [[0RB005001_保圧|保圧]] の")
    assert "## タイムライン\n- [ ] 09:00 打ち合わせ" in t
    run_once(box, now=NOW)
    assert text(daily).count(TITLE) == 1                     # 書き換えて、重ねない
    write(yu / "05_ナレッジ/0RB005001_保圧.md",
          '---\nid: 0RB005001\nauthor: Yu\ntype: ナレッジ\nvisibility: 個人\n---\n')
    run_once(box, now=NOW)
    assert text(daily) == "# 2026-10-24\n\n## タイムライン\n- [ ] 09:00 打ち合わせ\n"   # 知らせがなくなれば消す


def test_friday_outlook_reminder(box):
    yu = box.personal
    friday = datetime(2026, 10, 30, 8, 0, tzinfo=ids.JST).timestamp()
    daily = write(yu / "00_日誌/デイリー/2026-10-30.md", "# 2026-10-30\n")
    run_once(box, now=friday)
    assert "見込みを更新してください: [[0RA00A001_試しPJ|試しPJ]]" in text(daily)
    assert "見込みを更新してください" in report(box)


def test_similar_references(box):
    yu, shared = box.personal, box.shared
    write(shared / "別PJ/0RA00B001_別PJ.md", "---\nid: 0RA00B001\ntype: プロジェクト\nmembers: [Yu]\n---\n")
    write(shared / "共通/02_ノード/0RA100001_ヒケ量.md", "---\nid: 0RA100001\ntype: ノード\nauthor: 佐藤\n---\n")
    write(shared / "別PJ/03_イシュー/0RA200001_前のヒケ.md",
          '---\nid: 0RA200001\nauthor: 佐藤\ntype: イシュー\nproject: [別PJ]\nfriend: ["[[0RA100001_ヒケ量]]"]\n---\n')
    write(shared / "別PJ/05_ナレッジ/0RA300001_保圧で減る.md",
          '---\nid: 0RA300001\nauthor: 佐藤\ntype: ナレッジ\nusefulness: A\n'
          'risk_reduction:\n  - "[[0RA200001_前のヒケ]] 出荷→小"\n---\n')
    write(shared / "別PJ/05_ナレッジ/0RA400001_役に立たない.md",
          '---\nid: 0RA400001\nauthor: 佐藤\ntype: ナレッジ\nusefulness: C\n'
          'risk_reduction:\n  - "[[0RA200001_前のヒケ]] 出荷→小"\n---\n')
    nid = ids.encode_time(ids.seconds_since_epoch(datetime.fromtimestamp(NOW, tz=ids.JST)) - 3600) + "001"
    p = write(yu / f"03_イシュー/{nid}_今のヒケ.md",
              f'---\nid: {nid}\nauthor: Yu\ntype: イシュー\nimpact: 出荷\nspeed: すぐ\nproject: [{PJ}]\n'
              'friend: ["[[0RA100001_ヒケ量]]"]\n---\n## リスク\n## 類似・参考ナレッジ\n説明の行\n\n## 次\n')
    old = write(yu / "03_イシュー/0A0000001_古いヒケ.md",
                f'---\nid: 0A0000001\nauthor: Yu\ntype: イシュー\nimpact: 出荷\nspeed: すぐ\nproject: [{PJ}]\n'
                'friend: ["[[0RA100001_ヒケ量]]"]\n---\n## 類似・参考ナレッジ\n')
    run_once(box, now=NOW)
    t = text(p)
    assert ("## 類似・参考ナレッジ\n説明の行\n- [[0RA300001_保圧で減る|保圧で減る]](ナレッジ、有用性 A)\n"
            "- [[0RA200001_前のヒケ|前のヒケ]](別PJ のイシュー)\n\n## 次\n") in t
    assert "役に立たない" not in t
    assert "前のヒケ" not in text(old)                       # 作ってから日がたったノートには足さない
    run_once(box, now=NOW + 60)
    assert text(p).count("[[0RA200001_") == 1              # 重ねない
