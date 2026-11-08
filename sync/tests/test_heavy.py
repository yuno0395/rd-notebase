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
def cloud(tmp_path):
    root = tmp_path / "Box"
    shared = root / "共有"
    data = root / "開発データ"
    data.mkdir(parents=True)
    write(shared / "_仕組み/tools/同期プログラム/メンバー.csv",
          "名前,記号,使い始めた日\n山田,001,2026-10-24\n田中,002,2026-10-24\n")
    write(shared / f"{PJ}/0RA00A001_{PJ}.md", "---\nid: 0RA00A001\ntype: プロジェクト\nmembers: [山田, 田中]\n---\n")

    def cfg(member, code, data_dir):
        personal = root / f"個人_{member}"
        write(personal / "_仕組み/個人設定.md", f'---\nname: {member}\n---\n')
        c = Config(member=member, personal=personal, shared=shared, shared_data=data_dir,
                   backup_dir=tmp_path / f"backup_{member}", state_dir=tmp_path / f"state_{member}",
                   idle_seconds=0)
        c.code = member_code(c)
        return c

    # 田中の PC では Box の場所が違う(同じ 開発データ を別のパスで見ている)
    kato_view = tmp_path / "田中のPC" / "開発データ"
    kato_view.parent.mkdir(parents=True)
    try:
        kato_view.symlink_to(data, target_is_directory=True)
    except OSError:  # Windows で権限がないときは、同じ場所で確かめる
        kato_view = data
    return {"data": data, "shared": shared, "yu": cfg("山田", "001", data), "kato": cfg("田中", "002", kato_view)}


def issue(c, nid="0RB001001", project=PJ, body="") -> Path:
    return write(c.personal / f"{project}/03_イシュー/{nid}_ヒケ.md",
                 f"---\nid: {nid}\nauthor: {c.member}\ntype: イシュー\nimpact: 出荷\nspeed: すぐ\n"
                 f"project: [{project}]\n---\n{body}")


def report(c) -> str:
    return text(c.personal / "_仕組み/同期レポート.md")


def test_moves_heavy_and_keeps_light(cloud):
    yu, data = cloud["yu"], cloud["data"]
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
    moved = data / "_個人/山田/0RB001001/成形条件.xlsx"
    assert moved.read_bytes() == b"xlsx"
    assert (data / "_個人/山田/0RB001001/長い.mp4").exists()
    assert not (att / "成形条件.xlsx").exists()
    assert (att / "写真.png").exists() and (att / "報告.pdf").exists() and (att / "短い.mp4").exists()
    t = text(note)
    assert f"[成形条件.xlsx]({file_url(moved)})" in t
    assert "![[_仕組み/attachments/0RB001001/写真.png]]" in t       # 画像はそのまま
    assert "重い添付を移した: _仕組み/attachments/0RB001001/成形条件.xlsx → 開発データ/_個人/山田/0RB001001/成形条件.xlsx" in report(yu)
    # 重い添付は共有 vault にコピーしない
    assert not (cloud["shared"] / "_仕組み/attachments/0RB001001/成形条件.xlsx").exists()
    assert (cloud["shared"] / "_仕組み/attachments/0RB001001/写真.png").exists()


def test_promote_to_project_and_shared_link_form(cloud):
    yu, data, shared = cloud["yu"], cloud["data"], cloud["shared"]
    note = issue(yu, body="![[_仕組み/attachments/0RB001001/成形条件.xlsx]]\n")
    write(yu.personal / "_仕組み/attachments/0RB001001/成形条件.xlsx", b"xlsx")
    run_once(yu, now=NOW)            # _個人 へ移し、ノートを共有へ集める
    run_once(yu, now=NOW + 60)       # 共有されたので プロジェクトへ移す(F-20)
    final = data / PJ / "0RB001001/成形条件.xlsx"
    assert final.read_bytes() == b"xlsx"
    assert not (data / "_個人/山田/0RB001001/成形条件.xlsx").exists()
    assert f"[成形条件.xlsx]({file_url(final)})" in text(note)
    run_once(yu, now=NOW + 120)      # 書き換えたノートを集める
    s = text(shared / f"{PJ}/03_イシュー/0RB001001_ヒケ.md")
    assert f"[成形条件.xlsx](開発データ/{PJ}/0RB001001/成形条件.xlsx)" in s   # 共有では相対パス(F-19)
    assert "file:///" not in s
    # 田中に配るときは、田中の PC の file:/// に直す
    run_once(cloud["kato"], now=NOW + 180)
    got = text(cloud["kato"].personal / f"{PJ}/03_イシュー/0RB001001_ヒケ.md")
    assert f"[成形条件.xlsx]({file_url(cloud['kato'].shared_data / PJ / '0RB001001/成形条件.xlsx')})" in got
    # 次の同期で、同じ内容とみなされて競合にならない
    run_once(yu, now=NOW + 240)
    run_once(cloud["kato"], now=NOW + 300)
    assert "競合" not in report(yu) and "競合" not in report(cloud["kato"])


def test_same_name_gets_suffix(cloud):
    yu, data = cloud["yu"], cloud["data"]
    issue(yu, body="![[_仕組み/attachments/0RB001001/a.xlsx]]\n")
    write(data / "_個人/山田/0RB001001/a.xlsx", b"old")
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"new")
    run_once(yu, now=NOW)
    assert (data / "_個人/山田/0RB001001/a.xlsx").read_bytes() == b"old"
    assert (data / "_個人/山田/0RB001001/a_2.xlsx").read_bytes() == b"new"


def test_no_data_root_reports(cloud):
    yu = cloud["yu"]
    yu.shared_data = None
    issue(yu)
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    run_once(yu, now=NOW)
    assert "開発データの場所が設定にありません: 重い添付が 1 件" in report(yu)
    assert (yu.personal / "_仕組み/attachments/0RB001001/a.xlsx").exists()


def test_dry_run_moves_nothing(cloud):
    yu = cloud["yu"]
    note = issue(yu, body="![[_仕組み/attachments/0RB001001/a.xlsx]]\n")
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    before = text(note)
    run_once(yu, dry_run=True, now=NOW)
    assert (yu.personal / "_仕組み/attachments/0RB001001/a.xlsx").exists()
    assert text(note) == before
    assert "予定: 重い添付を移した" in report(yu)


def test_link_forms():
    root = Path("C:/Users/tanaka/Box/開発データ")
    url = file_url(root / "PJ/0RB001001/成形 条件.xlsx")
    assert url == "file:///C:/Users/tanaka/Box/%E9%96%8B%E7%99%BA%E3%83%87%E3%83%BC%E3%82%BF/PJ/0RB001001/%E6%88%90%E5%BD%A2%20%E6%9D%A1%E4%BB%B6.xlsx"
    s = to_shared(f"見て [条件]({url}) と [他](https://example.com)", root)
    assert s == "見て [条件](<開発データ/PJ/0RB001001/成形 条件.xlsx>) と [他](https://example.com)"
    assert to_personal(s, root) == f"見て [条件]({url}) と [他](https://example.com)"
    # ファイル名だけのリンクは、その id のノートの中だけ直す
    t = "![[成形条件.xlsx]] と ![[_仕組み/attachments/0RB001001/成形条件.xlsx|条件表]]"
    assert relink(t, "0RB001001", "成形条件.xlsx", "U", True) == "[成形条件.xlsx](U) と [条件表](U)"
    assert relink(t, "0RB001001", "成形条件.xlsx", "U", False) == "![[成形条件.xlsx]] と [条件表](U)"


def test_recover_shared(cloud, capsys):
    from notesync.__main__ import main
    import yaml
    shared, data, yu = cloud["shared"], cloud["data"], cloud["yu"]
    write(shared / f"{PJ}/03_イシュー/直接書いた.md", "---\ntype: イシュー\n---\n[[参考メモ]] を見る\n")
    write(shared / f"{PJ}/03_イシュー/0RB009002_古い.md",
          "---\nid: 0RB009002\nauthor: 田中\ntype: イシュー\n---\n![[_仕組み/attachments/0RB009002/測定.csv]]\n")
    write(shared / "_仕組み/attachments/0RB009002/測定.csv", "a,b\n")
    write(shared / "共通/02_ノード/参考メモ.md", "---\ntype: ノード\n---\n")
    # 配布物のマニュアルは id をつけず、リンクも書き換えない
    manual = "# 初期設定\n[[02_チームメンバー_普段の仕事]] と [[参考メモ]]\n"
    write(shared / "00_マニュアル/01_チームメンバー_初期設定.md", manual)
    write(shared / "00_マニュアル/02_チームメンバー_普段の仕事.md", "# 普段の仕事\n")
    run_once(yu, now=NOW)
    r = report(yu)
    assert "拾い直し: 共有 vault に id のないノートが 2 件あります" in r
    assert "00_マニュアル" not in r
    assert "拾い直し: 共有 vault の _仕組み/attachments/ に重い添付が 1 件あります" in r
    cfg_path = write(yu.personal.parent / "config.yaml", yaml.safe_dump({
        "member": "山田", "personal": str(yu.personal), "shared": str(shared), "shared_data": str(data),
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
    assert (shared / "00_マニュアル/01_チームメンバー_初期設定.md").read_text(encoding="utf-8") == manual
    assert (shared / "00_マニュアル/02_チームメンバー_普段の仕事.md").exists()
    run_once(yu, now=NOW + 60)
    assert "拾い直し" not in report(yu)


def test_link_forms_on_nas():
    """NAS などのネットワークの場所(\\\\nas\\共有\\...)も、行って戻って同じリンクになる。"""
    from pathlib import PureWindowsPath
    root = PureWindowsPath(r"\\nas\チーム\開発データ")
    url = file_url(root / "PJ/a.xlsx")
    assert url.startswith("file://nas/") and not url.startswith("file:///")
    s = to_shared(f"[a]({url})", root)
    assert s == "[a](開発データ/PJ/a.xlsx)"
    assert to_personal(s, root) == f"[a]({url})"


# ---------- F-17c: 共有しないノートの重い添付は自分用へ ----------

def private_issue(c, nid="0RB001001", vis="個人", body="![[_仕組み/attachments/0RB001001/a.xlsx]]\n") -> Path:
    # 共有しない(PIP・古い 個人)ノートは 00_PIP/メモ/ に置く(v0.91)
    where = "00_PIP/メモ" if vis in ("個人", "PIP", "[PIP]") else f"{PJ}/03_イシュー"
    return write(c.personal / f"{where}/{nid}_ヒケ.md",
                 f"---\nid: {nid}\nauthor: {c.member}\ntype: イシュー\nimpact: 出荷\nspeed: すぐ\n"
                 f"project: [{PJ}]\nvisibility: {vis}\n---\n{body}")


def test_private_note_goes_to_private_data(cloud, tmp_path):
    yu, data = cloud["yu"], cloud["data"]
    yu.private_data = tmp_path / "Box/個人/開発データ_自分用"
    yu.private_data.parent.mkdir(parents=True, exist_ok=True)  # なければ同期が作る
    note = private_issue(yu)
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    write(yu.personal / "_仕組み/attachments/0RB001001/写真.png", b"png")
    run_once(yu, now=NOW)
    moved = yu.private_data / "0RB001001/a.xlsx"
    assert moved.read_bytes() == b"x"
    assert not (data / "_個人").exists()                     # チームが見られる場所には出さない
    assert (yu.personal / "_仕組み/attachments/0RB001001/写真.png").exists()
    assert f"[a.xlsx]({file_url(moved)})" in text(note)
    assert "重い添付を移した: _仕組み/attachments/0RB001001/a.xlsx → 自分用/0RB001001/a.xlsx" in report(yu)


def test_diary_and_memo_attachments_go_to_private_data(cloud, tmp_path):
    yu, data = cloud["yu"], cloud["data"]
    yu.private_data = tmp_path / "Box/個人/開発データ_自分用"
    yu.private_data.parent.mkdir(parents=True, exist_ok=True)  # なければ同期が作る
    daily = write(yu.personal / "00_日誌/2026-10-24.md", "![[_仕組み/attachments/日誌/2026-10-24/測定.csv]]\n")
    write(yu.personal / "_仕組み/attachments/日誌/2026-10-24/測定.csv", b"1,2")
    memo = write(yu.personal / "00_日誌/メモ/0RC001001_打合せ.md",
                 "---\nid: 0RC001001\ntype: メモ\nvisibility: 個人\n---\n![[_仕組み/attachments/0RC001001/b.zip]]\n")
    write(yu.personal / "_仕組み/attachments/0RC001001/b.zip", b"zip")
    run_once(yu, now=NOW)
    assert (yu.private_data / "日誌/2026-10-24/測定.csv").read_bytes() == b"1,2"
    assert (yu.private_data / "0RC001001/b.zip").read_bytes() == b"zip"
    assert not (data / "_個人").exists()
    assert file_url(yu.private_data / "日誌/2026-10-24/測定.csv") in text(daily)
    assert file_url(yu.private_data / "0RC001001/b.zip") in text(memo)


def test_private_without_setting_stays_in_vault(cloud):
    yu, data = cloud["yu"], cloud["data"]
    private_issue(yu)
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    run_once(yu, now=NOW)
    assert (yu.personal / "_仕組み/attachments/0RB001001/a.xlsx").exists()
    assert not (data / "_個人").exists()
    assert "自分用の添付の場所が設定にありません: 共有しないノートの重い添付が 1 件" in report(yu)


def test_switch_private_and_team(cloud, tmp_path):
    yu, data = cloud["yu"], cloud["data"]
    yu.private_data = tmp_path / "Box/個人/開発データ_自分用"
    yu.private_data.parent.mkdir(parents=True, exist_ok=True)  # なければ同期が作る
    # 前の版で 開発データ/_個人/ へ移していた添付は、自分用へ移す
    note = private_issue(yu, body=f"[a.xlsx]({file_url(data / '_個人/山田/0RB001001/a.xlsx')})\n")
    write(data / "_個人/山田/0RB001001/a.xlsx", b"x")
    run_once(yu, now=NOW)
    assert (yu.private_data / "0RB001001/a.xlsx").exists()
    assert not (data / "_個人/山田/0RB001001/a.xlsx").exists()
    assert f"[a.xlsx]({file_url(yu.private_data / '0RB001001/a.xlsx')})" in text(note)
    assert "共有しないノートなので添付を自分用へ移した" in report(yu)
    # 共有するノートに変えたら(「共有する」ボタンでプロジェクトのフォルダへ移す)、開発データ へ戻す(共有されたらプロジェクトへ)
    moved_note = yu.personal / f"{PJ}/03_イシュー/{note.name}"
    moved_note.parent.mkdir(parents=True, exist_ok=True)
    moved_note.write_text(text(note).replace("visibility: 個人", "visibility: チーム"), encoding="utf-8")
    note.unlink()
    note = moved_note
    run_once(yu, now=NOW + 60)
    run_once(yu, now=NOW + 120)
    final = data / PJ / "0RB001001/a.xlsx"
    assert final.read_bytes() == b"x"
    assert not (yu.private_data / "0RB001001/a.xlsx").exists()
    assert f"[a.xlsx]({file_url(final)})" in text(note)


def test_deleted_private_note_keeps_files_private(cloud, tmp_path):
    yu, data = cloud["yu"], cloud["data"]
    yu.private_data = tmp_path / "Box/個人/開発データ_自分用"
    yu.private_data.parent.mkdir(parents=True, exist_ok=True)
    write(yu.private_data / "0RB009001/a.xlsx", b"x")   # ノートはもう消した
    run_once(yu, now=NOW)
    assert (yu.private_data / "0RB009001/a.xlsx").exists()
    assert not (data / "_個人").exists()


def test_changing_private_data_copies_and_relinks(cloud, tmp_path):
    """private_data を書き換えたら、前のフォルダの添付をすべて新しいフォルダへコピーしてリンクを直す。"""
    yu = cloud["yu"]
    old = tmp_path / "Box/個人/開発データ_自分用"
    old.parent.mkdir(parents=True, exist_ok=True)
    yu.private_data = old
    note = private_issue(yu)
    write(yu.personal / "_仕組み/attachments/0RB001001/a.xlsx", b"x")
    daily = write(yu.personal / "00_日誌/2026-10-24.md", "![[_仕組み/attachments/日誌/2026-10-24/測定 1.csv]]\n")
    write(yu.personal / "_仕組み/attachments/日誌/2026-10-24/測定 1.csv", b"1,2")
    run_once(yu, now=NOW)
    assert (old / "0RB001001/a.xlsx").exists()
    # 名前を変える
    new = tmp_path / "Box/個人/山田の添付"
    yu.private_data = new
    run_once(yu, now=NOW + 60)
    assert (new / "0RB001001/a.xlsx").read_bytes() == b"x"
    assert (new / "日誌/2026-10-24/測定 1.csv").read_bytes() == b"1,2"
    assert (old / "0RB001001/a.xlsx").exists()                 # 前のフォルダは消さない
    assert f"[a.xlsx]({file_url(new / '0RB001001/a.xlsx')})" in text(note)
    assert file_url(new / "日誌/2026-10-24/測定 1.csv") in text(daily)
    assert file_url(old / "0RB001001/a.xlsx") not in text(note)
    assert "自分用の添付の場所を変えたので、2 件を" in report(yu)
    # 次の同期ではもうしない
    run_once(yu, now=NOW + 120)
    assert report(yu).count("自分用の添付の場所を変えたので、") == 1


def test_changing_private_data_to_missing_old_reports(cloud, tmp_path):
    yu = cloud["yu"]
    base = tmp_path / "Box/個人"
    base.mkdir(parents=True, exist_ok=True)
    (yu.state_dir).mkdir(parents=True, exist_ok=True)
    (yu.state_dir / "自分用の添付の場所_前回.txt").write_text(str(base / "消えた"), encoding="utf-8")
    yu.private_data = base / "新しい"
    run_once(yu, now=NOW)
    assert "前の自分用の添付のフォルダ" in report(yu) and "見つからない" in report(yu)
