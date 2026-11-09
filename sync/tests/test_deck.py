"""F-59・F-59b: 説明資料。筋書きごとに、載せるノート・並び・足りないところ・社外向けの絞り込みと、
Excalidraw の図(共通の図・ひな形・機密区分・引用)・つなぐ・PDF の写しを確かめる。"""

import json
from datetime import date
from pathlib import Path

import pytest

from notesync import deck, deck_draw
from notesync.now import run_now, take_signals

PJ = "試しPJ"
TODAY = date(2026, 11, 8)
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def note(root, rel, fid, typ, body="", **fm):
    lines = [f"id: {fid}", f"type: {typ}"]
    for k, v in fm.items():
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    return write(root / rel, "---\n" + "\n".join(lines) + "\n---\n" + body)


def L(fid, name):
    return f"[[{fid}_{name}|{name}]]"


@pytest.fixture
def shared(tmp_path):
    s = tmp_path / "共有"
    write(s / "_仕組み/templates/設計案.md", "---\ntype: 設計案\n---\n## この案の中身\nどんな構造か。図は Ctrl+D\n## どの条件ならこの案が勝つか\n")
    note(s, f"{PJ}/0RB0004XGV_{PJ}.md", "0RB0004XGV", "プロジェクト",
         "## 期間・主な節目\n| 節目 | 計画日 | 見込み日 |\n| --- | --- | --- |\n| DR1 | 2026-11-20 | 2026-11-27 |\n",
         request_to_manager="試作の予算を決めてほしい")
    note(s, f"{PJ}/01_目的/0RB0014XGV_軽くする.md", "0RB0014XGV", "目的",
         "## 誰に何を届けるか\n現場の人に軽い工具\n## 達成の判定基準\n500 g 以下\n", project=[PJ])
    note(s, f"{PJ}/01_目的/0RB0024XGV_持ち運べる.md", "0RB0024XGV", "仮説", "## この仮説\n片手で持てれば売れる\n",
         parent=[L("0RB0014XGV", "軽くする")])
    note(s, f"{PJ}/01_設計案/0RB0034XGV_樹脂化.md", "0RB0034XGV", "設計案",
         "## この案の中身\nどんな構造か。図は Ctrl+D\n筐体を [[0RB0094XGV_PA66|PA66]] にする\n## どの条件ならこの案が勝つか\n肉厚 2 mm 以上\n",
         parent=[L("0RB0014XGV", "軽くする")], 価値仮説=[L("0RB0024XGV", "持ち運べる")], aliases=["樹脂の筐体"],
         author=["229999_山田"], image=["_仕組み/attachments/0RB0034XGV/fig_0RB0034XGV_樹脂化.excalidraw.svg"])
    write(s / "_仕組み/attachments/0RB0034XGV/fig_0RB0034XGV_樹脂化.excalidraw.svg", SVG)
    note(s, f"{PJ}/01_設計案/0RB0054XGV_マグネシウム.md", "0RB0054XGV", "設計案", "## この案の中身\n鋳造\n",
         parent=[L("0RB0014XGV", "軽くする")], status="不採用")
    note(s, f"{PJ}/01_設計案/0RB0064XGV_アルミ.md", "0RB0064XGV", "設計案", "## この案の中身\n板金\n",
         parent=[L("0RB0014XGV", "軽くする")])
    note(s, f"{PJ}/03_イシュー/0RB0044XGV_割れる.md", "0RB0044XGV", "イシュー",
         "## リスク\n落とすと割れる\n## 減らす方法\nリブを足す\n", project=[PJ], impact="方針",
         脅かす=[L("0RB0034XGV", "樹脂化")])
    note(s, f"{PJ}/04_タスク/0RB0074XGV_落下試験.md", "0RB0074XGV", "タスク",
         "## やること\n1 m から落とす\n## 完了の条件\n10 回で割れない\n## リスクはどう変わったか\n方針→絞込\n",
         parent=[L("0RB0044XGV", "割れる")], status="完了", due="2026-11-01", author=["229999_山田"])
    note(s, f"{PJ}/04_タスク/0RB0084XGV_型を頼む.md", "0RB0084XGV", "タスク", "## やること\n型屋に頼む\n",
         parent=[L("0RB0044XGV", "割れる")], status="待ち", due="2026-11-05")
    note(s, f"{PJ}/05_ナレッジ/0RB00A4XGV_リブで割れない.md", "0RB00A4XGV", "ナレッジ",
         "## 結論\nリブ 1 mm で割れない\n## 次に気をつけること\nヒケに注意\n",
         parent=[L("0RB0074XGV", "落下試験")], risk_reduction=[f"{L('0RB0044XGV', '割れる')} 方針→絞込"])
    note(s, "共通/02_ノード/0RB0094XGV_PA66.md", "0RB0094XGV", "ノード", "## これは何か\nナイロン\n")
    note(s, f"{PJ}/04_タスク/0RB00B4XGV_試験片を作る.md", "0RB00B4XGV", "実験・試作記録",
         "## 目的と仮説\n強度を確かめる\n## 条件\n| 項目 | 値 |\n| --- | --- |\n| 温度 | 80 ℃ |\n## 測定結果\n52 MPa\n## 判定\n合格\n",
         parent=[L("0RB0044XGV", "割れる")], author=["229999_山田"])
    note(s, "共通/02_ノード/0RB00C4XGV_ねじ.md", "0RB00C4XGV", "ノード",
         "## これは何か\nM3 のねじ\n## PartsList\n| 品名 | 個数 | 単価 | 発注先 |\n| --- | --- | --- | --- |\n| M3 | 4 | 10 | A社 |\n",
         kind="部品")
    note(s, f"{PJ}/04_タスク/0RB00D4XGV_秘密の試験.md", "0RB00D4XGV", "タスク", "## やること\nA社の\n",
         secret_refs=["[[0RX00A4XGV_案件A|案件A]]"])
    return s


def personal_note(tmp_path, shared, rel):
    """個人 vault の同じノート(合図は個人 vault のパスで来る)。"""
    p = tmp_path / "個人" / rel
    write(p, (shared / rel).read_text(encoding="utf-8"))
    return p


def make(tmp_path, shared, rel, story, ask=""):
    return deck.build(shared, personal_note(tmp_path, shared, rel), story, ask, "山田", TODAY)


def drawn(tmp_path, shared, rel, story, ask=""):
    """個人 vault に資料の図を作り、(資料の図の中身, 共通の図の中身, 資料の図のパス) を返す。"""
    personal_note(tmp_path, shared, rel)
    path, d = deck.make(shared, tmp_path / "個人", rel, story, ask, "山田", TODAY)
    common = path.with_name(path.name.replace(".excalidraw.md", "_共通.excalidraw.md"))
    return path.read_text(encoding="utf-8"), common.read_text(encoding="utf-8"), path


def texts(drawing: str) -> str:
    """図のページに出る文字だけ。"""
    _, els, _ = deck_draw.load_text(drawing)
    return "\n".join(e.get("originalText", "") for e in els if e["type"] == "text")


def titles(d):
    return [s.title for s in d.slides]


DESIGN = f"{PJ}/01_設計案/0RB0034XGV_樹脂化.md"
ISSUE = f"{PJ}/03_イシュー/0RB0044XGV_割れる.md"


def test_inform_from_design(tmp_path, shared):
    d = make(tmp_path, shared, DESIGN, "知ってもらう")
    t = titles(d)
    assert t[0] == "樹脂の筐体" and t[1] == "要点" and t[2] == "全体の形" and t[-1] == "足りないところ"
    # なんのため(目的・仮説) → どう実現するか(案) → 何が不安か → 何がわかったか
    assert t.index("軽くする") < t.index("持ち運べる") < t.index("樹脂の筐体", 1) < t.index("割れる") < t.index("リブで割れない")
    s = next(x for x in d.slides if x.kind == "note" and x.title == "樹脂の筐体")
    body = dict(s.sections)["この案の中身"]
    assert "Ctrl+D" not in body            # テンプレートの説明の行は出さない
    assert "PA66" in body and "0RB0094XGV" not in body   # リンクは名前だけ
    assert s.image == SVG
    assert s.refs == [("0RB0034XGV", "樹脂の筐体")]       # 引用はもとのノートの id と名前
    assert "作成 山田" in s.foot


def test_gaps_listed(tmp_path, shared):
    d = make(tmp_path, shared, DESIGN, "知ってもらう")
    gaps = {(a, b) for a, b in d.gaps}
    assert ("軽くする", "図がない(Ctrl+D で枠 Summary に描く)") in gaps
    assert ("リブで割れない", "確認者(reviewed_by)がいない") in gaps
    assert d.slides[-1].rows == d.gaps


def test_inform_from_knowledge_is_result(tmp_path, shared):
    d = make(tmp_path, shared, f"{PJ}/05_ナレッジ/0RB00A4XGV_リブで割れない.md", "知ってもらう")
    t = titles(d)
    assert t[2] == "リブで割れない" and "割れる" in t and "落下試験" in t and "次に気をつけること" in t


def test_opinion_issue_and_from_task(tmp_path, shared):
    d = make(tmp_path, shared, ISSUE, "意見をもらう", "リブ以外に手はあるか")
    t = titles(d)
    assert t[2] == "聞きたいこと" and t[-2] == "聞きたいこと"
    assert d.slides[2].big == "リブ以外に手はあるか"
    assert t.index("樹脂の筐体") < t.index("割れる", 1) < t.index("落下試験") < t.index("リブで割れない") < t.index("いまの考え方")
    d2 = make(tmp_path, shared, f"{PJ}/04_タスク/0RB0074XGV_落下試験.md", "意見をもらう")
    assert "割れる" in titles(d2)   # タスクなら親のイシューが中心


def test_opinion_design_lists_candidates(tmp_path, shared):
    d = make(tmp_path, shared, DESIGN, "意見をもらう", "もっと軽い案は")
    cmp_ = next(s for s in d.slides if s.title == "候補の比較")
    assert [r[0] for r in cmp_.rows] == ["樹脂の筐体", "アルミ"]   # 不採用は比較に入れない
    assert cmp_.rows[0][3] == "1"                               # 方針リスク 未解決
    gone = next(s for s in d.slides if s.title == "外した案とその理由")
    assert gone.faded and gone.rows[0][0] == "マグネシウム"


def test_opinion_wrong_type(tmp_path, shared):
    with pytest.raises(deck.DeckError, match="イシューか設計案"):
        make(tmp_path, shared, f"{PJ}/01_目的/0RB0014XGV_軽くする.md", "意見をもらう")


def test_decide_from_project(tmp_path, shared):
    d = make(tmp_path, shared, f"{PJ}/0RB0004XGV_{PJ}.md", "決めてもらう")
    assert d.slides[2].big == "試作の予算を決めてほしい"      # 台帳の request_to_manager
    summary = dict(d.slides[1].sections)
    assert summary["候補"] == "2 件"
    assert "アルミ" in summary["参考"]                       # 方針リスクのいちばん少ない案
    risks = next(s for s in d.slides if s.title == "候補ごとの残りのリスク")
    assert risks.rows == [["樹脂の筐体", "割れる", "方針", ""]]


def test_decide_from_minutes(tmp_path, shared):
    note(shared, f"{PJ}/0RB00E4XGV_DR1.md", "0RB00E4XGV", "議事録",
         f"## 議題\n{L('0RB0034XGV', '樹脂化')} と {L('0RB0064XGV', 'アルミ')} のどちらにするか\n## 解像度の判定\n段階2\n",
         kind="DR")
    d = make(tmp_path, shared, f"{PJ}/0RB00E4XGV_DR1.md", "決めてもらう")
    assert "樹脂化" in d.slides[2].big and "0RB0034XGV" not in d.slides[2].big
    assert "解像度" in titles(d)


def test_schedule(tmp_path, shared):
    d = make(tmp_path, shared, ISSUE, "予定を確かめる")
    assert d.title == PJ
    stones = next(s for s in d.slides if s.title == "節目")
    assert stones.rows == [["DR1", "2026-11-20", "2026-11-27", "+7 日"]]
    late = next(s for s in d.slides if s.title == "遅れ・期限切れのタスク")
    assert [r[0] for r in late.rows] == ["型を頼む"]
    wait_ = next(s for s in d.slides if s.title == "待ちのタスク")
    assert wait_.rows[0][0] == "型を頼む"
    assert dict(d.slides[1].sections)["判断してほしいこと"] == "試作の予算を決めてほしい"


def test_outside_experiment_hides_results(tmp_path, shared):
    html, _, _ = drawn(tmp_path, shared, f"{PJ}/04_タスク/0RB00B4XGV_試験片を作る.md", "社外へ仕様を伝える")
    assert "80 ℃" in html and "強度を確かめる" in html
    assert "52 MPa" not in html and "合格" not in html          # 結果は出さない
    assert PJ not in html and "割れる" not in html               # プロジェクト名・ほかのノートの名前
    assert "足りないところ" not in html and "山田" in html          # 問い合わせ先は名前だけ
    assert "229999" not in html
    page = texts(html)                                  # ページに出る文字(customData の控えは PDF に出ない)
    assert "引用: 試験片を作る" in page and "0RB00B4XGV" not in page   # 社外向けは id を伏せる


def test_outside_part_hides_price(tmp_path, shared):
    html, _, _ = drawn(tmp_path, shared, "共通/02_ノード/0RB00C4XGV_ねじ.md", "社外へ仕様を伝える")
    assert "M3" in html and "個数" in html
    assert "単価" not in html and "A社" not in html and "｜ 10" not in html


def test_outside_refuses_secret_and_wrong_type(tmp_path, shared):
    with pytest.raises(deck.DeckError, match="機密"):
        make(tmp_path, shared, f"{PJ}/04_タスク/0RB00D4XGV_秘密の試験.md", "社外へ仕様を伝える")
    with pytest.raises(deck.DeckError, match="実験"):
        make(tmp_path, shared, DESIGN, "社外へ仕様を伝える")


def test_not_shared(tmp_path, shared):
    p2 = write(tmp_path / "個人/共通/02_ノード/0RB00G4XGV_まだ.md", "---\nid: 0RB00G4XGV\ntype: ノード\n---\n")
    with pytest.raises(deck.DeckError, match="共有していない"):
        deck.build(shared, p2, "知ってもらう", "", "山田", TODAY)


def test_pip_note_is_confidential(tmp_path, shared):
    """PIP のノートからも作れる(個人 vault の中身で)。機密区分は Confidential、報告フォルダには写さない。"""
    p = write(tmp_path / "個人/00_PIP/メモ/0RB00F4XGV_売上.md",
              "---\nid: 0RB00F4XGV\ntype: ノード\nvisibility: PIP\n---\n## これは何か\n売上の見込み\n")
    with pytest.raises(deck.DeckError, match="PIP"):
        deck.build(shared, p, "知ってもらう", "", "山田", TODAY)          # 個人 vault を渡さなければ作らない
    d = deck.build(shared, p, "知ってもらう", "", "山田", TODAY, tmp_path / "個人")
    assert d.label == "Confidential" and d.pip and d.title == "売上"
    path, _ = deck.make(shared, tmp_path / "個人", "00_PIP/メモ/0RB00F4XGV_売上.md", "知ってもらう", "", "山田", TODAY)
    assert "deck_report: \"\"" in path.read_text(encoding="utf-8")


def test_note_limit(tmp_path, shared):
    for k in range(25):
        fid = f"0RC{k:03d}4XGV"
        note(shared, f"{PJ}/03_イシュー/{fid}_懸念{k}.md", fid, "イシュー", "## リスク\nx\n",
             脅かす=[L("0RB0034XGV", "樹脂化")])
    d = make(tmp_path, shared, DESIGN, "知ってもらう")
    assert sum(1 for s in d.slides if s.kind == "note") == deck.MAX_NOTES
    assert any(s.title.startswith("何が不安か: ほかに") for s in d.slides)


def test_out_path_never_overwrites(tmp_path, shared):
    """資料の図は 00_PIP/説明資料/ に置き、同じ名前があれば _2 を付ける(手直しを消さない)。"""
    _, _, p1 = drawn(tmp_path, shared, DESIGN, "知ってもらう")
    _, _, p2 = drawn(tmp_path, shared, DESIGN, "知ってもらう")
    assert p1.parent == tmp_path / "個人" / "00_PIP" / "説明資料"
    assert p1.name == "知ってもらう_樹脂の筐体_2026-11-08.excalidraw.md"
    assert p2.name == "知ってもらう_樹脂の筐体_2026-11-08_2.excalidraw.md"
    assert p1.with_name("知ってもらう_樹脂の筐体_2026-11-08_共通.excalidraw.md").is_file()


def test_default_story():
    assert deck.default_story("設計案") == "意見をもらう"
    assert deck.default_story("議事録") == "決めてもらう"
    assert deck.default_story("プロジェクト") == "予定を確かめる"
    assert deck.default_story("ノード", "部品") == "社外へ仕様を伝える"
    assert deck.default_story("目的") == "知ってもらう"


def test_signal_makes_deck(tmp_path, shared, cfg, monkeypatch):
    """合図に「資料」があれば、同期のあとに作って結果に HTML の場所を書く。"""
    cfg.shared, cfg.report_dir = shared, tmp_path / "報告"
    p = personal_note(tmp_path, shared, DESIGN)
    sig = tmp_path / "今すぐ"
    sig.mkdir()
    write(sig / "1.json", json.dumps({"vault": str(cfg.personal),
                                     "資料": {"note": str(p), "筋書き": "知ってもらう", "ひとこと": ""}}))
    decks = {}
    results = take_signals(sig, cfg.personal, decks=decks)
    assert decks[sig / "1.done.json"]["筋書き"] == "知ってもらう"
    from notesync.report import Report
    run_now(cfg, results, lambda c: Report(), decks)
    res = json.loads((sig / "1.done.json").read_text(encoding="utf-8"))
    assert res["ok"] and "説明資料を作りました" in res["message"], res
    assert res["open"].startswith("00_PIP/説明資料/知ってもらう_樹脂の筐体_")
    assert (cfg.personal / res["open"]).is_file()


def test_signal_error_is_reported(tmp_path, shared, cfg):
    cfg.shared = shared
    sig = tmp_path / "今すぐ"
    sig.mkdir()
    write(sig / "1.json", json.dumps({"vault": str(cfg.personal),
                                     "資料": {"note": str(tmp_path / "x.md"), "筋書き": "知ってもらう"}}))
    decks = {}
    from notesync.report import Report
    run_now(cfg, take_signals(sig, cfg.personal, decks=decks), lambda c: Report(), decks)
    res = json.loads((sig / "1.done.json").read_text(encoding="utf-8"))
    assert not res["ok"] and "id のない" in res["message"]


# ---------- F-59b: 機密区分・範囲・Excalidraw の図 ----------

def scope(**kw):
    from notesync.visibility import Scope
    return Scope(**kw)


def test_label_from_visibility():
    """EXT は <相手>+<会社名>/Confidential、Internal はそのまま、PJ は <PJ>/Confidential、PIP は Confidential。"""
    assert deck.label_of(scope(ext=["EXT_A社"], projects=["ABC"]), "〇〇株式会社", False) == "A社+〇〇株式会社/Confidential"
    assert deck.label_of(scope(ext=["EXT_A社", "EXT_B社"]), "", False) == "A社+B社/Confidential"
    assert deck.label_of(scope(internal=True), "〇〇株式会社", False) == "Internal use only"
    assert deck.label_of(scope(projects=["ABC", "DEF"]), "〇〇株式会社", False) == "ABC+DEF/Confidential"
    assert deck.label_of(scope(), "", True) == "Confidential"


def test_only_notes_in_range(tmp_path, shared):
    """Internal use only のノートから作った資料には、プロジェクト名だけのノートは載せない。"""
    note(shared, "共通/02_ノード/0RB00H4XGV_樹脂の知識.md", "0RB00H4XGV", "ノード", "## これは何か\nPA66 は吸水する\n",
         visibility="Internal use only", parent=[L("0RB0034XGV", "樹脂化")])
    d = make(tmp_path, shared, "共通/02_ノード/0RB00H4XGV_樹脂の知識.md", "知ってもらう")
    assert d.label == "Internal use only"
    assert "樹脂の筐体" not in [s.title for s in d.slides if s.kind == "note"]
    assert ["樹脂の筐体", "範囲が狭いので載せていません"] in d.gaps
    d2 = make(tmp_path, shared, DESIGN, "知ってもらう")
    assert d2.label == f"{PJ}/Confidential"


def test_ext_note_hides_ids_and_names_partner(tmp_path, shared):
    write(shared / "_仕組み/同期設定.yaml", "会社名: 〇〇株式会社\n")
    note(shared, f"{PJ}/04_タスク/0RB00J4XGV_外注試験.md", "0RB00J4XGV", "タスク", "## やること\n引張試験\n",
         visibility=[PJ, "EXT_A社"])
    d = make(tmp_path, shared, f"{PJ}/04_タスク/0RB00J4XGV_外注試験.md", "知ってもらう")
    assert d.label == "A社+〇〇株式会社/Confidential" and d.hide_ids
    html, common, _ = drawn(tmp_path, shared, f"{PJ}/04_タスク/0RB00J4XGV_外注試験.md", "知ってもらう")
    assert "0RB00J4XGV" not in texts(html) and "引用: 外注試験" in texts(html)
    assert "A社+〇〇株式会社/Confidential" in texts(common) and "〇〇株式会社" in texts(common)


def test_drawing_pages_and_common(tmp_path, shared):
    """1ページ = 16:9 のフレーム。共通の図を各ページに絵で貼って固定し、番号・章・引用はページごとの文字。"""
    write(tmp_path / "個人/_仕組み/個人設定.md", '---\nname: "山田"\naffiliation: "開発部 第2グループ"\n---\n')
    html, common, path = drawn(tmp_path, shared, DESIGN, "知ってもらう")
    _, els, files = deck_draw.load(path)
    frames = deck_draw.frames_of(els)
    assert frames[0]["name"] == "01 樹脂の筐体" and frames[1]["name"] == "02 要点"
    assert all(f["width"] == 1600 and f["height"] == 900 for f in frames)
    n = len(frames)
    for f in frames:
        kids = [e for e in els if e.get("frameId") == f["id"]]
        base = [e for e in kids if (e.get("customData") or {}).get("deck_common")]
        assert len(base) == 1 and base[0]["locked"] and base[0]["width"] == 1600
        link = files[base[0]["fileId"]]
        assert link.endswith("_共通.excalidraw#^clippedframe=" + ("deck_cover" if f is frames[0] else "deck_page"))
    t = texts(html)
    assert f"2 / {n}" in t and f"{n} / {n}" in t                    # ページの番号
    assert "引用: 0RB0034XGV 樹脂の筐体" in t                          # 引用は id と名前
    assert "■ この案の中身" in t
    c = texts(common)
    assert "樹脂の筐体" in c and f"{PJ}/Confidential" in c and "開発部 第2グループ 山田" in c
    assert "文書番号: " in c and "{文書番号}" not in c                 # 文書番号は空(あとで書き込む)
    assert "{ページ}" not in c                                        # ページの番号は共通に入れない
    links = [files[e["fileId"]] for e in els if e["type"] == "image" and not (e.get("customData") or {}).get("deck_common")]
    assert any(v.endswith("fig_0RB0034XGV_樹脂化.excalidraw.svg") for v in links)   # 図の SVG を貼る
    kplex = next(v for v in links if v.endswith("全体の形.svg"))
    assert "<style>" in (tmp_path / "個人" / kplex).read_text(encoding="utf-8")   # K-Plex の形は色の決まりを入れて置く
    assert '"deck_report": ' not in html and f'deck_report: "{PJ}"' in html


def test_custom_template(tmp_path, shared):
    """ひな形: 枠の中の線・文字・ロゴを写し、言葉を置き換え、「本文」の四角に中身、色の四角でテーマカラー。"""
    sc = deck_draw.Scene()
    sc.frame(0, 0, "ページ", fid="fr")
    sc.text(100, 20, "{会社名} 社外秘", 20, "#000000", "fr")
    sc.text(1500, 860, "p.{ページ}", 16, "#000000", "fr", align="right")
    sc.box(200, 100, 1200, 700, "本文", 20, "#000000", "fr", stroke="#000000")
    sc.box(1700, 0, 200, 80, "メイン色", 20, "#ffffff", None, bg="#aa0000")
    logo = write(shared / "_仕組み/説明資料のひな形/logo.png", "png")
    sc.image(20, 10, 60, 40, "logo.png", "fr")
    write(shared / deck_draw.TEMPLATE_DIR / "ページ.excalidraw.md", deck_draw.dump(sc.els, sc.files))
    write(shared / "_仕組み/同期設定.yaml", "会社名: 〇〇株式会社\n")
    html, common, path = drawn(tmp_path, shared, DESIGN, "知ってもらう")
    c = texts(common)
    assert "〇〇株式会社 社外秘" in c and "本文" not in c and "メイン色" not in c
    assert "p.2" in texts(html)
    _, els, files = deck_draw.load(path)
    title = next(e for e in els if e["type"] == "text" and e.get("originalText") == "要点")
    assert title["strokeColor"] == "#aa0000"                          # メイン色
    assert 200 <= title["x"] and 100 <= title["y"] - 1100              # 本文の四角の中(2ページ目)
    assert any(v.endswith("logo.png") for v in deck_draw.load(path.with_name(path.name.replace(".excalidraw.md", "_共通.excalidraw.md")))[2].values())
    assert logo.is_file()


def test_broken_template_falls_back(tmp_path, shared):
    write(shared / deck_draw.TEMPLATE_DIR / "ページ.excalidraw.md", "---\nexcalidraw-plugin: parsed\n---\n```compressed-json\nxx\n```\n")
    personal_note(tmp_path, shared, DESIGN)
    path, d = deck.make(shared, tmp_path / "個人", DESIGN, "知ってもらう", "", "山田", TODAY)
    assert ["(ひな形)", "ひな形を読めませんでした"] in d.gaps and path.is_file()


def test_distributed_templates_are_valid(tmp_path):
    """配るひな形は読めて、本文の範囲と色がある。"""
    root = Path(__file__).resolve().parents[2] / "vault/共有" / deck_draw.TEMPLATE_DIR
    for kind in ("ページ", "表紙"):
        t = deck_draw.read_template(root / f"{kind}.excalidraw.md", None)
        assert t.colors == {"main": deck_draw.MAIN, "accent": deck_draw.ACCENT}
        assert t.has("{機密区分}") and t.has("{文書番号}")
    assert deck_draw.read_template(root / "ページ.excalidraw.md", None).has("{引用}")


def test_join_decks(tmp_path, shared):
    """つなぐ: 表紙は1つ目だけ、2つ目からは区切りのページ、番号は通し、機密区分は選んだもの。"""
    _, _, p1 = drawn(tmp_path, shared, DESIGN, "知ってもらう")
    _, _, p2 = drawn(tmp_path, shared, f"{PJ}/04_タスク/0RB00B4XGV_試験片を作る.md", "社外へ仕様を伝える")
    per = tmp_path / "個人"
    out = deck_draw.join_decks([p1, p2], per, "Internal use only", True, TODAY)
    assert out.name == "つないだ資料_樹脂の筐体_2026-11-08.excalidraw.md"
    fm, els, files = deck_draw.load(out)
    frames = deck_draw.frames_of(els)
    kinds = [(f.get("customData") or {}).get("deck_kind") for f in frames]
    assert kinds.count("cover") == 1 and "divider" in kinds and kinds.count("gaps") == 1 and kinds[-1] == "gaps"
    assert [f["name"][:2] for f in frames] == [f"{i:02d}" for i in range(1, len(frames) + 1)]
    t = texts(out.read_text(encoding="utf-8"))
    assert f"{len(frames)} / {len(frames)}" in t
    assert "引用: 0RB00B4XGV 試験片を作る" in t                       # 社内向けにすると社外向けのページにも id
    common = out.with_name(out.name.replace(".excalidraw.md", "_共通.excalidraw.md"))
    assert "Internal use only" in texts(common.read_text(encoding="utf-8"))
    assert all(v.startswith("00_PIP/説明資料/つないだ資料_") for k, v in files.items() if "clippedframe" in v)
    assert fm["deck_report"] == PJ and p1.is_file() and p2.is_file()
    out2 = deck_draw.join_decks([p2], per, "Confidential", False, TODAY)
    assert "0RB00B4XGV" not in texts(out2.read_text(encoding="utf-8"))
    assert deck_draw.load(out2)[0]["deck_report"] == ""


def test_copy_pdfs(tmp_path, shared):
    """00_PIP/説明資料/ の PDF のうち、共有に出ているノートの社内向けの資料のものだけを報告フォルダへ写す。"""
    _, _, p1 = drawn(tmp_path, shared, DESIGN, "知ってもらう")
    _, _, p2 = drawn(tmp_path, shared, f"{PJ}/04_タスク/0RB00B4XGV_試験片を作る.md", "社外へ仕様を伝える")
    write(p1.with_name(p1.name.replace(".excalidraw.md", ".pdf")), "%PDF")
    write(p2.with_name(p2.name.replace(".excalidraw.md", "-pages.pdf")), "%PDF")
    rep = tmp_path / "報告"
    got = deck.copy_pdfs(tmp_path / "個人", rep)
    assert got == [rep / PJ / "説明資料" / "知ってもらう_樹脂の筐体_2026-11-08.pdf"] and got[0].is_file()
    assert deck.copy_pdfs(tmp_path / "個人", rep) == []                 # 新しくなければ写さない
    assert deck.copy_pdfs(tmp_path / "個人", None) == []


def test_affiliation_line_added(tmp_path):
    f = write(tmp_path / "個人/_仕組み/個人設定.md", '---\nname: "山田"\nnumber: "229999"\n---\n# 個人設定\n')
    assert deck.add_affiliation(tmp_path / "個人")
    text = f.read_text(encoding="utf-8")
    assert 'number: "229999"\naffiliation: ""' in text and text.endswith("# 個人設定\n")
    assert not deck.add_affiliation(tmp_path / "個人")                  # 何度でも同じ
    from notesync import frontmatter
    assert frontmatter.load(text)["affiliation"] == ""
