"""F-29: 管理者向けの週報。"""

from datetime import date
from pathlib import Path

import openpyxl
import pytest

from notesync.report import Report
from notesync.weekly import make_weekly, maybe_weekly

PJ = "樹脂カバー"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def note(shared, folder, nid, name, fm):
    return write(shared / folder / f"{nid}_{name}.md", f"---\nid: {nid}\n{fm}---\n本文\n")


@pytest.fixture
def shared(tmp_path):
    s = tmp_path / "共有"
    write(s / "_仕組み/同期設定.yaml", "report_runner: yu\n")
    note(s, PJ, "0RA001001", PJ,
         "type: プロジェクト\nmembers: [Yu, 佐藤]\nstatus: 進行中\nmilestones:\n"
         "  - {name: DR1, plan: 2026-11-07, forecast: 2026-11-21}\noutlook: △\n"
         "outlook_reason: 金型の納期が2週遅れ\nrequest_to_manager: 試作費の追加を判断してほしい\n")
    note(s, f"{PJ}/01_目的", "0RA002001", "部品コスト3割減", "type: 目的\nproject: [樹脂カバー]\n")
    note(s, f"{PJ}/01_目的", "0RA003001", "3割減なら採用される",
         'type: 仮説\nstatus: 検証中\nparent: ["[[0RA002001_部品コスト3割減]]"]\n')
    note(s, f"{PJ}/01_目的", "0RA004001", "外れた話", 'type: 仮説\nstatus: 外れた\nparent: ["[[0RA002001_部品コスト3割減]]"]\n')
    note(s, "共通/02_ノード", "0RA005001", "肉厚", "type: ノード\nvalue_kind: 独立\n")
    note(s, "共通/02_ノード", "0RA006001", "ヒケ量", "type: ノード\nvalue_kind: 組み立て\n")
    note(s, f"{PJ}/03_イシュー", "0RB001001", "ヒケ",
         'author: Yu\ntype: イシュー\nstatus: 対策中\nimpact: 絞込\nspeed: すぐ\nproject: [樹脂カバー]\n'
         'parent: ["[[0RA003001_3割減なら採用される]]"]\nfriend: ["[[0RA006001_ヒケ量]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RB002001", "寸法",
         'author: 佐藤\ntype: イシュー\nstatus: 低減済み\nimpact: 出荷\nspeed: すぐ\nresolution: 設計空間\n'
         'project: [樹脂カバー]\nparent: ["[[0RA003001_3割減なら採用される]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RB003001", "迷子", "author: Yu\ntype: イシュー\nstatus: 未対応\nimpact: 中\nproject: [樹脂カバー]\n")
    note(s, f"{PJ}/03_イシュー", "0RB004001", "外れ先",
         'author: Yu\ntype: イシュー\nstatus: 未対応\nimpact: 中\nproject: [樹脂カバー]\nparent: ["[[0RA004001_外れた話]]"]\n')
    for i, st in enumerate(["完了", "完了", "進行中"]):
        note(s, f"{PJ}/04_タスク", f"0RB10{i}001", f"対策{i}",
             f'author: Yu\ntype: タスク\nstatus: {st}\ndue: 2026-10-20\nparent: ["[[0RB001001_ヒケ]]"]\n')
    note(s, f"{PJ}/04_タスク", "0RB200002", "待ち", 'author: 佐藤\ntype: タスク\nstatus: 待ち\nparent: ["[[0RB002001_寸法]]"]\n')
    note(s, f"{PJ}/議事録", "0RB300001", "DR0", "type: 議事録\ndate: 2026-10-01\n")
    for i, st in enumerate(["候補", "不採用", "候補"]):
        note(s, f"{PJ}/設計記録", f"0RB40{i}001", f"センサー案{i}",
             f'type: 設計記録\nstatus: {st}\nparent: ["[[0RB001001_ヒケ]]"]\n')
    # 別のプロジェクトが同じノードを使う
    note(s, "別PJ", "0RC001001", "別PJ", "type: プロジェクト\nmembers: [Yu]\n")
    note(s, "別PJ/03_イシュー", "0RC002001", "別のヒケ",
         'author: Yu\ntype: イシュー\nproject: [別PJ]\nfriend: ["[[0RA006001_ヒケ量]]"]\n')
    write(s / "_仕組み/記録/ノート履歴/Yu.csv",
          "日時,id,名前,種類,項目,前,後\n"
          "2026-10-02 09:00,0RB100001,対策0,タスク,status,進行中,完了\n"
          "2026-10-10 09:00,0RB101001,対策1,タスク,status,進行中,完了\n"
          "2026-10-03 09:00,0RB102001,対策2,タスク,due,2026-10-06,2026-10-13\n"
          "2026-10-10 09:00,0RB102001,対策2,タスク,due,2026-10-13,2026-10-20\n"
          "2026-10-05 09:00,0RA001001,樹脂カバー,プロジェクト,outlook,,△\n")
    return s


def test_weekly_report(shared, tmp_path):
    out = tmp_path / "報告"
    r = Report()
    made = make_weekly(shared, out, date(2026, 10, 26), r)
    assert [p.name for p in made] == ["2026-W44.md", "2026-W44.md"]
    md = (out / PJ / "2026-W44.md").read_text(encoding="utf-8")
    assert "- 見込み: **△**" in md and "金型の納期が2週遅れ" in md and "試作費の追加" in md
    assert "見込み未更新" in md                                   # 最後の更新から21日
    assert "| 部品コスト3割減 | 50%(1/2) | 1 | 0 | 1 | 0 |" in md
    assert "| DR1 | 2026-11-07 | 2026-11-21 | +14 日 |" in md
    assert "| イシュー | 迷子 | Yu | 仮説につながっていない |" in md
    assert "外れた仮説につながっている(外れた話)" in md
    assert "| ヒケ | 別PJ | 別のヒケ | ヒケ量 |" in md
    assert "DR(2026-10-01)のあと対策 2 件完了、resolution は 未把握 のまま" in md
    assert "原因が組み立て値のまま(ヒケ量)" in md
    assert "| 対策2 | Yu | 期限を 2 回延ばした |" in md
    assert "| Yu | 1 | 0 | 1 | 0 |" in md and "| 佐藤 | 0 | 1 | 0 | 0 |" in md
    assert "| ヒケ | 2 |" in md                                     # センサー案 3 つのうち不採用でない 2 つ
    wb = openpyxl.load_workbook(out / PJ / "2026-W44.xlsx")
    assert "担当者" in wb.sheetnames and wb["見込み"]["B2"].value == "△"
    # 2回目は作らない。次の週は推移が伸びる
    assert make_weekly(shared, out, date(2026, 10, 27), Report()) == []
    (shared / f"{PJ}/設計記録/0RB402001_センサー案2.md").write_text(
        (shared / f"{PJ}/設計記録/0RB402001_センサー案2.md").read_text(encoding="utf-8").replace("候補", "不採用"),
        encoding="utf-8")
    make_weekly(shared, out, date(2026, 11, 2), Report())
    assert "| ヒケ | 2→1 |" in (out / PJ / "2026-W45.md").read_text(encoding="utf-8")


def test_only_runner_on_monday(shared, tmp_path):
    out = tmp_path / "報告"
    from datetime import datetime
    from notesync.ids import JST
    monday = datetime(2026, 10, 26, 8, tzinfo=JST).timestamp()
    maybe_weekly("佐藤", shared, out, monday, Report(), False)
    assert not out.exists()
    maybe_weekly("Yu", shared, out, monday - 86400, Report(), False)  # 日曜
    assert not out.exists()
    maybe_weekly("Yu", shared, out, monday, Report(), False)
    assert (out / PJ / "2026-W44.md").exists()
