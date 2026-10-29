"""F-29: 管理者向けの週報。"""

from datetime import date
from pathlib import Path

import pytest

from notesync.report import Report
from notesync.weekly import make_weekly, maybe_weekly
from notesync.weekly_html import row_html


def row(*cells):
    return row_html(list(cells))

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
    # 仮説の木: 外れた仮説の下の仮説につながる仕事も「外れた」。反論のついた仮説は週報に出す
    note(s, f"{PJ}/01_目的", "0RA007001", "下の仮説", 'type: 仮説\nstatus: 検証中\nparent: ["[[0RA004001_外れた話]]"]\n')
    note(s, f"{PJ}/01_目的", "0RA008001", "金型で3割減る",
         'type: 仮説\nstatus: 検証中\nparent: ["[[0RA003001_3割減なら採用される]]"]\nchallenger: ["[[0RA005001_肉厚]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RB005001", "下の仮説の仕事",
         'author: Yu\ntype: イシュー\nstatus: 未対応\nimpact: 中\nproject: [樹脂カバー]\nparent: ["[[0RA007001_下の仮説]]"]\n')
    note(s, "共通/02_ノード", "0RA005001", "肉厚", "type: ノード\nvalue_kind: 独立\n")
    note(s, "共通/02_ノード", "0RA006001", "ヒケ量", "type: ノード\nvalue_kind: 組み立て\n")
    note(s, f"{PJ}/03_イシュー", "0RB001001", "ヒケ",
         'author: Yu\ntype: イシュー\nstatus: 対策中\nimpact: 絞込\nspeed: すぐ\nproject: [樹脂カバー]\n'
         'parent: ["[[0RB400001_センサー案0]]"]\nfriend: ["[[0RA006001_ヒケ量]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RB002001", "寸法",
         'author: 佐藤\ntype: イシュー\nstatus: 低減済み\nimpact: 出荷\nspeed: すぐ\nresolution: 設計空間\n'
         'project: [樹脂カバー]\nparent: ["[[0RA003001_3割減なら採用される]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RB003001", "迷子", "author: Yu\ntype: イシュー\nstatus: 未対応\nimpact: 中\nproject: [樹脂カバー]\n")
    # 優先順位は低いのに一部だけ進めたもの(中途半端な仕事)と、手をつけていないもの
    note(s, f"{PJ}/03_イシュー", "0RB006001", "梱包の手間",
         "author: 佐藤\ntype: イシュー\nstatus: 未対応\nimpact: 小\npriority: 4\nproject: [樹脂カバー]\n")
    note(s, f"{PJ}/03_イシュー", "0RB007001", "手つかず",
         "author: 佐藤\ntype: イシュー\nstatus: 未対応\nimpact: 小\npriority: 4\nproject: [樹脂カバー]\n")
    note(s, f"{PJ}/04_タスク", "0RB202001", "箱を試す",
         'author: 佐藤\ntype: タスク\nstatus: 完了\nparent: ["[[0RB006001_梱包の手間]]"]\n')
    note(s, f"{PJ}/04_タスク", "0RB203001", "箱を直す",
         'author: 佐藤\ntype: タスク\nstatus: 未着手\nparent: ["[[0RB006001_梱包の手間]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RB004001", "外れ先",
         'author: Yu\ntype: イシュー\nstatus: 未対応\nimpact: 中\nproject: [樹脂カバー]\nparent: ["[[0RA004001_外れた話]]"]\n')
    for i, st in enumerate(["完了", "完了", "進行中"]):
        note(s, f"{PJ}/04_タスク", f"0RB10{i}001", f"対策{i}",
             f'author: Yu\ntype: タスク\nstatus: {st}\ndue: 2026-10-20\nparent: ["[[0RB001001_ヒケ]]"]\n')
    note(s, f"{PJ}/04_タスク", "0RB200002", "待ち", 'author: 佐藤\ntype: タスク\nstatus: 待ち\nparent: ["[[0RB002001_寸法]]"]\n')
    note(s, f"{PJ}/04_タスク", "0RB201001", "見てほしい",
         'author: Yu\ntype: タスク\nstatus: 確認待ち\nreview_request: [佐藤]\nparent: ["[[0RB001001_ヒケ]]"]\n')
    note(s, f"{PJ}/議事録", "0RB300001", "DR0", "type: 議事録\ndate: 2026-09-20\n")
    # kind: DR なら名前に DR がなくても DR とみなす
    note(s, f"{PJ}/議事録", "0RB301001", "仕様の見直し", "type: 議事録\nkind: DR\ndate: 2026-10-01\n")
    note(s, f"{PJ}/議事録", "0RB302001", "打ち合わせ", "type: 議事録\ndate: 2026-10-05\n")
    # 設計案の候補は同じ parent で一組になる。ソリューション(v0.54 まで)・設計記録(v0.37 まで)も設計案として数える
    for i, (tp, st) in enumerate([("設計案", "候補"), ("ソリューション", "不採用"), ("設計記録", "候補")]):
        note(s, f"{PJ}/01_設計案", f"0RB40{i}001", f"センサー案{i}",
             f'type: {tp}\nstatus: {st}\nparent: ["[[0RA003001_3割減なら採用される]]"]\n')
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
          "2026-10-05 09:00,0RA001001,樹脂カバー,プロジェクト,outlook,,△\n"
          "2026-10-08 09:00,0RB202001,箱を試す,タスク,status,進行中,完了\n")
    return s


def test_weekly_report(shared, tmp_path):
    out = tmp_path / "報告"
    r = Report()
    made = make_weekly(shared, out, date(2026, 10, 26), r)
    assert [p.name for p in made] == ["2026-W44.html", "2026-W44.html"]
    md = (out / PJ / "2026-W44.html").read_text(encoding="utf-8")
    assert "試作費の追加" in md                                   # 管理者に判断してほしいことは書いてあれば出す
    assert "金型の納期が2週遅れ" not in md and "見込み未更新" not in md   # 見込みは載せない(Yu 2026-10-29)
    assert "開発の目処(成果物候補ごと)" in md
    assert row('DR1', '2026-11-07', '2026-11-21', '+14 日') in md
    assert row('梱包の手間', '4', '佐藤', '完了 1・進行中 0・未着手 1', '2026-10-08') in md
    assert "<td>手つかず</td>" not in md
    assert row('Yu', '1', '0', '1', '1', '0') in md and row('佐藤', '0', '1', '0', '0', '1') in md
    assert row('3割減なら採用される', '2') in md                                     # センサー案 3 つのうち不採用でない 2 つ
    # 載せない節(Yu 2026-10-29)。出荷準備度は開発の後の方で載せる。同じノードは既定で外す
    for gone in ("出荷準備度", "目的に沿っていない", "反論のついた仮説", "行き詰まり", "機密", "他のプロジェクトと同じノード"):
        assert gone not in md, gone
    assert not list(out.rglob("*.md")) and not list(out.rglob("*.xlsx"))   # HTML 1つだけ
    index = (out / "週報の一覧.html").read_text(encoding="utf-8")
    assert f'href="{PJ}/2026-W44.html"' in index
    # 2回目は作らない。次の週は推移が伸びる
    assert make_weekly(shared, out, date(2026, 10, 27), Report()) == []
    (shared / f"{PJ}/01_設計案/0RB402001_センサー案2.md").write_text(
        (shared / f"{PJ}/01_設計案/0RB402001_センサー案2.md").read_text(encoding="utf-8").replace("候補", "不採用"),
        encoding="utf-8")
    make_weekly(shared, out, date(2026, 11, 2), Report())
    assert row('3割減なら採用される', '2→1') in (out / PJ / "2026-W45.html").read_text(encoding="utf-8")


def test_anyone_on_monday(shared, tmp_path):
    """誰の PC でも月曜に作る(report_runner は読まない)。同じ週の分は作り直さない。"""
    out = tmp_path / "報告"
    from datetime import datetime
    from notesync.ids import JST
    monday = datetime(2026, 10, 26, 8, tzinfo=JST).timestamp()
    maybe_weekly(shared, out, monday - 86400, Report(), False)  # 日曜
    assert not out.exists()
    maybe_weekly(shared, out, monday, Report(), False)
    page = out / PJ / "2026-W44.html"
    assert page.exists()
    assert not (out / "週報を作っています.lock").exists()
    page.write_text("手で直した", encoding="utf-8")
    maybe_weekly(shared, out, monday + 3600, Report(), False)
    assert page.read_text(encoding="utf-8") == "手で直した"


def test_weekly_waits_for_other_pc(shared, tmp_path):
    import json
    from datetime import datetime
    from notesync.ids import JST
    out = tmp_path / "報告"
    monday = datetime(2026, 10, 26, 8, tzinfo=JST).timestamp()
    write(out / "週報を作っています.lock", json.dumps({"pc": "SATO-PC", "time": monday - 60}))
    r = Report()
    maybe_weekly(shared, out, monday, r, False)
    assert not (out / PJ).exists()
    assert any("SATO-PC" in x for x in r.records)


def test_sections_can_be_chosen(shared, tmp_path):
    out = tmp_path / "報告"
    # チーム設定で出荷準備度を載せ、同じノードを「自動」にする
    (shared / "_仕組み/同期設定.yaml").write_text(
        "report_sections:\n  出荷準備度: true\n  同じノード: 自動\n  担当者: false\n", encoding="utf-8")
    make_weekly(shared, out, date(2026, 10, 26), Report())
    html = (out / PJ / "2026-W44.html").read_text(encoding="utf-8")
    assert row('部品コスト3割減', '50%(1/2)', '1', '0', '1', '0') in html
    assert row('ヒケ', '別PJ', '別のヒケ', 'ヒケ量') in html
    assert "担当者ごとのタスク" not in html
    # 「自動」: ほかに進めているプロジェクトがなければ載せない
    p = next((shared / "別PJ").glob("0RC001001_*.md"))
    p.write_text(p.read_text(encoding="utf-8").replace("members: [Yu]", "members: [Yu]\nstatus: 完了"), encoding="utf-8")
    make_weekly(shared, out, date(2026, 10, 26), Report(), force=True)
    html = (out / PJ / "2026-W44.html").read_text(encoding="utf-8")
    assert "他のプロジェクトと同じノード" not in html and "出荷準備度(目的ごと)" in html


def test_sections_only_and_hide(shared):
    from notesync.weekly import sections_of
    s = sections_of(shared, hide=["担当者"])
    assert s["担当者"] is False and s["同じノード"] is False and s["出荷準備度"] is False
    s = sections_of(shared, only=["出荷準備度"])
    assert [k for k, v in s.items() if v] == ["出荷準備度"]


def test_prospects(tmp_path):
    """開発の目処(Yu 2026-10-29): 不可能ではない成果物候補ごとに、方針リスクの解決数と未解決数。
    候補の下の部分の案につくリスクも数える。"""
    s = tmp_path / "共有"
    write(s / "_仕組み/同期設定.yaml", "")
    note(s, PJ, "0RA001001", PJ, "type: プロジェクト\nmembers: [Yu]\nstatus: 進行中\n")
    g = '["[[0RA002001_予兆検知]]"]'
    note(s, f"{PJ}/01_目的", "0RA002001", "予兆検知", "type: 目的\nproject: [樹脂カバー]\n")
    note(s, f"{PJ}/01_目的", "0RA003001", "電池3年", f"type: 仮説\nstatus: 検証中\nparent: {g}\n")
    note(s, f"{PJ}/01_設計案", "0RB001001", "A案クランプ式", f"type: 設計案\nstatus: 候補\nparent: {g}\n")
    note(s, f"{PJ}/01_設計案", "0RB002001", "電池ユニット",
         'type: 設計案\nstatus: 候補\nparent: ["[[0RB001001_A案クランプ式]]"]\n価値仮説: ["[[0RA003001_電池3年]]"]\n')
    note(s, f"{PJ}/01_設計案", "0RB004001", "B案ねじ止め式", f"type: 設計案\nstatus: 候補\nparent: {g}\n")
    note(s, f"{PJ}/01_設計案", "0RB005001", "C案", f"type: 設計案\nstatus: 不採用\nparent: {g}\n")
    issue = "author: Yu\ntype: イシュー\nproject: [樹脂カバー]\n"
    note(s, f"{PJ}/03_イシュー", "0RC001001", "無線で電池3年もつか",
         issue + 'status: 対策中\nimpact: 方針\n脅かす: ["[[0RB002001_電池ユニット]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RC002001", "クランプが成り立つか",
         issue + 'status: 解消\nimpact: 方針\nparent: ["[[0RB001001_A案クランプ式]]"]\n')   # 古い書き方の parent も読む
    note(s, f"{PJ}/03_イシュー", "0RC003001", "重い", issue + 'status: 未対応\nimpact: 出荷\n脅かす: ["[[0RB001001_A案クランプ式]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RC004001", "やめた", issue + 'status: 中止\nimpact: 方針\n脅かす: ["[[0RB004001_B案ねじ止め式]]"]\n')
    note(s, f"{PJ}/03_イシュー", "0RC005001", "市場があるか", issue + 'status: 未対応\nimpact: 方針\n脅かす: ["[[0RA003001_電池3年]]"]\n')
    out = tmp_path / "報告"
    make_weekly(s, out, date(2026, 10, 26), Report())
    html = (out / PJ / "2026-W44.html").read_text(encoding="utf-8")
    assert row("予兆検知", "A案クランプ式", "候補", "1", "1") in html
    assert row("予兆検知", "B案ねじ止め式", "候補", "0", "0") in html
    # 候補ごとの K-Plex 風の図: 中心に候補、左に仮説、右に脅かすイシュー、下に部分の案
    assert html.count('<svg class="kp"') == 2
    assert "<title>A案クランプ式</title>" in html and "部分の案: 電池ユニット" in html
    assert "クランプが成り立つか(priority -、方針、解決)" in html
    assert "<td>C案</td>" not in html
    assert "不可能ではない成果物候補: 2 件(不採用・中止にした候補: 1 件)" in html
    assert "どの候補にもつかない方針リスク(仮説を脅かすものなど): 解決 0 件、未解決 1 件" in html


def test_topics(shared, tmp_path):
    """今週のトピック(Yu 2026-10-29): 台帳の本文に PL が選んだノートとダイジェストを書き、
    週報に今週の動き(ノート履歴の7日分と、下のタスクの完了)を添えて載せる。"""
    p = next((shared / PJ).glob("0RA001001_*.md"))
    p.write_text(p.read_text(encoding="utf-8").replace(
        "本文\n",
        "## 今週のトピック\n説明の行\n- [[0RB001001_ヒケ|ヒケ]]: 保圧を上げたらヒケが半分になった\n"
        "- [[0RB006001_梱包の手間]]\n- [[  ]]: 今週のダイジェスト\n- 金型メーカーと打ち合わせ\n\n![[00_今週動いたノート.base]]\n## 次の章\n- [[0RB003001_迷子]]: 載らない\n"),
        encoding="utf-8")
    with (shared / "_仕組み/記録/ノート履歴/Yu.csv").open("a", encoding="utf-8") as f:
        f.write("2026-10-22 09:00,0RB001001,ヒケ,イシュー,status,未対応,対策中\n"
                "2026-10-23 09:00,0RB201001,見てほしい,タスク,status,進行中,完了\n"
                "2026-10-10 09:00,0RB001001,ヒケ,イシュー,resolution,,現象\n")   # 先週より前は出さない
    out = tmp_path / "報告"
    make_weekly(shared, out, date(2026, 10, 26), Report())
    html = (out / PJ / "2026-W44.html").read_text(encoding="utf-8")
    assert row("ヒケ", "イシュー", "保圧を上げたらヒケが半分になった",
               "status 未対応→対策中(10-22)、タスク「見てほしい」完了(10-23)") in html
    assert row("梱包の手間", "イシュー", "(未記入)", "記録された変化なし") in html
    assert row("", "", "金型メーカーと打ち合わせ", "") in html
    assert "<td>今週のダイジェスト</td>" not in html                     # テンプレートのままの行は出さない
    assert "載らない" not in html and "00_今週動いたノート" not in html
    assert html.index("今週のトピック") < html.index("開発の目処(成果物候補ごと)")


def test_topics_empty(shared, tmp_path):
    out = tmp_path / "報告"
    make_weekly(shared, out, date(2026, 10, 26), Report())
    assert "今週は書かれていません" in (out / PJ / "2026-W44.html").read_text(encoding="utf-8")
