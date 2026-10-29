"""F-53: 工程表(マイルストーンとタスクのガントチャート)。"""

from datetime import date, datetime
from pathlib import Path

from notesync import ids
from notesync.report import Report
from notesync.safety import Backup
from notesync.schedule import update_schedules
from notesync.vault import load_note, needs_id
from notesync.weekly import make_weekly

PJ = "樹脂カバー"
TODAY = date(2026, 11, 2)
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=ids.JST).timestamp()


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def setup(tmp_path):
    shared, personal = tmp_path / "共有", tmp_path / "個人"
    (personal / "90_共有").mkdir(parents=True)
    ledger = write(shared / PJ / f"0RA001001_{PJ}.md",
                   "---\nid: 0RA001001\ntype: プロジェクト\nmembers: [Yu]\nstatus: 進行中\n---\n"
                   "## 期間・主な節目\n説明\n\n| 節目 | 計画日 | 見込み日 |\n| --- | --- | --- |\n"
                   "| DR1 | 2026-11-10 | 2026-11-20 |\n\n## 今週のトピック\n- \n")
    write(shared / PJ / "03_イシュー/0RB001001_ヒケ.md",
          "---\nid: 0RB001001\ntype: イシュー\nstatus: 対策中\nproject: [樹脂カバー]\n---\n")
    write(shared / PJ / "04_タスク/0RC001001_保圧を変える.md",
          '---\nid: 0RC001001\ntype: タスク\nstatus: 完了\ndue: 2026-10-30\nparent: ["[[0RB001001_ヒケ|ヒケ]]"]\n---\n')
    write(shared / PJ / "04_タスク/0RC002001_リブを足す.md",
          '---\nid: 0RC002001\ntype: タスク\nstatus: 進行中\nparent: ["[[0RB001001_ヒケ|ヒケ]]"]\n---\n')
    write(shared / PJ / "04_タスク/0RC003001_まだ.md",
          '---\nid: 0RC003001\ntype: タスク\nstatus: 未着手\nparent: ["[[0RB001001_ヒケ|ヒケ]]"]\n---\n')
    write(shared / "_仕組み/記録/ノート履歴/Yu.csv",
          "日時,id,名前,種類,項目,前,後\n"
          "2026-10-20T10:00:00+09:00,0RC001001,保圧を変える,タスク,status,未着手,進行中\n"
          "2026-10-24T10:00:00+09:00,0RC001001,保圧を変える,タスク,status,進行中,完了\n"
          "2026-10-27T10:00:00+09:00,0RC002001,リブを足す,タスク,status,未着手,進行中\n")
    return shared, personal, ledger


def run(shared, personal, tmp_path, report=None):
    report = report or Report(dry_run=False)
    update_schedules(personal, shared, "Yu", report, Backup(tmp_path / "bk"), False, NOW, 0)
    return report


def test_writes_gantt_and_embeds_once(tmp_path):
    shared, personal, ledger = setup(tmp_path)
    run(shared, personal, tmp_path)
    out = shared / PJ / f"00_工程表_{PJ}.md"
    text = out.read_text(encoding="utf-8")
    assert "```mermaid\ngantt" in text
    assert "DR1 計画 :milestone, 2026-11-10, 0d" in text
    assert "DR1 見込み :crit, milestone, 2026-11-20, 0d" in text   # 遅れは赤
    assert "section ヒケ" in text
    assert "保圧を変える :done, 2026-10-20, 5d" in text
    assert "リブを足す :active, 2026-10-27, 7d" in text          # 今日まで伸ばす
    assert "まだ" not in text.split("```")[1]                       # 着手していないものは出さない
    # 各自の 90_共有 にも置く(台帳の埋め込みが切れないように)
    assert (personal / "90_共有" / PJ / f"00_工程表_{PJ}.md").read_text(encoding="utf-8") == text
    # 台帳の節目の表の下に1回だけ埋め込む
    body = ledger.read_text(encoding="utf-8")
    assert body.count(f"![[00_工程表_{PJ}]]") == 1
    assert body.index("| DR1 |") < body.index("![[00_工程表_") < body.index("## 今週のトピック")
    # もう一度走らせても変わらない
    r = run(shared, personal, tmp_path)
    assert ledger.read_text(encoding="utf-8") == body
    assert not [x for x in r.records if "工程表" in x]
    assert not r.warnings


def test_generated_file_gets_no_id(tmp_path):
    shared, personal, _ = setup(tmp_path)
    run(shared, personal, tmp_path)
    p = shared / PJ / f"00_工程表_{PJ}.md"
    assert not needs_id(load_note(shared, p, p.relative_to(shared)))


def test_started_before_records_is_guessed(tmp_path):
    shared, personal, _ = setup(tmp_path)
    write(shared / PJ / "04_タスク/0RC004001_記録なし.md",
          '---\nid: 0RC004001\ntype: タスク\nstatus: 進行中\nparent: ["[[0RB001001_ヒケ|ヒケ]]"]\n---\n')
    run(shared, personal, tmp_path)
    text = (shared / PJ / f"00_工程表_{PJ}.md").read_text(encoding="utf-8")
    start = ids.decode_time("0RC004001").date().isoformat()
    assert f"| 記録なし | ヒケ | {start}(推定) |" in text


def test_weekly_has_gantt_section(tmp_path):
    shared, personal, _ = setup(tmp_path)
    out = tmp_path / "報告"
    make_weekly(shared, out, TODAY, Report(dry_run=False))
    html = next(out.glob(f"{PJ}/*.html")).read_text(encoding="utf-8")
    assert "工程表" in html and 'class="kp gt"' in html
    assert "保圧を変える: 2026-10-20 〜 2026-10-24(完了)" in html
