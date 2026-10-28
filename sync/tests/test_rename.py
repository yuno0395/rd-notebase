"""同期のあとに名前を変えても、共有と二重にならない(id は変えない)。"""

from notesync.run import run_once

from .conftest import text
from .test_share import PJ, box, files, report, write  # noqa: F401

FIG_OLD = "_仕組み/attachments/0RB003001/図.excalidraw.md"
FIG_NEW = "_仕組み/attachments/0RB003001/fig_0RB003001_保圧を変える.excalidraw.md"


def test_renamed_note_moves_in_shared_and_links_follow(box):
    run_once(box["yu"])
    run_once(box["sato"])
    yu = box["yu"].personal
    (yu / "02_ノード/0RB001001_水.md").rename(yu / "02_ノード/0RB001001_お水.md")  # Obsidian の外で変えた
    run_once(box["yu"])
    s = files(box["shared"])
    assert "共通/02_ノード/0RB001001_お水.md" in s
    assert "共通/02_ノード/0RB001001_水.md" not in s
    assert "[[0RB001001_お水|水]]" in text(yu / "03_イシュー/0RB002001_ヒケ.md")   # 古いリンクを直す
    assert "[[0RB001001_お水|水]]" in text(box["shared"] / f"{PJ}/03_イシュー/0RB002001_ヒケ.md")
    run_once(box["sato"])
    p = files(box["sato"].personal)
    assert "90_共有/共通/02_ノード/0RB001001_お水.md" in p
    assert "90_共有/共通/02_ノード/0RB001001_水.md" not in p


def test_renamed_attachment_is_not_doubled(box):
    run_once(box["yu"])
    run_once(box["sato"])
    yu = box["yu"].personal
    (yu / FIG_OLD).rename(yu / FIG_NEW)
    run_once(box["yu"])
    s = files(box["shared"])
    assert FIG_NEW in s and FIG_OLD not in s
    assert FIG_OLD not in files(yu)                      # 共有から戻ってこない
    assert "添付の名前の変更か削除を反映" in report(box["yu"])
    run_once(box["sato"])
    p = files(box["sato"].personal)
    assert FIG_NEW in p and FIG_OLD not in p
    # もう一度回しても変わらない
    run_once(box["yu"])
    assert FIG_OLD not in files(yu) and FIG_OLD not in files(box["shared"])


def test_renamed_attachment_keeps_other_side_if_changed(box):
    run_once(box["yu"])
    yu = box["yu"].personal
    (yu / FIG_OLD).rename(yu / FIG_NEW)
    write(box["shared"] / FIG_OLD, "共有で描き足した\n")
    run_once(box["yu"])
    assert text(box["shared"] / FIG_OLD) == "共有で描き足した\n"
    assert "変わっているので残しています" in report(box["yu"])


def test_deleting_distributed_attachment_does_not_touch_shared(box):
    run_once(box["yu"])
    run_once(box["sato"])
    (box["sato"].personal / FIG_OLD).unlink()
    run_once(box["sato"])
    assert FIG_OLD in files(box["shared"])
    assert FIG_OLD in files(box["sato"].personal)        # 配られたものは戻る


def test_missing_folder_deletes_nothing(box):
    run_once(box["yu"])
    import shutil
    shutil.rmtree(box["shared"] / "_仕組み/attachments/0RB003001")
    run_once(box["yu"])
    assert FIG_OLD in files(box["yu"].personal)
    assert FIG_OLD in files(box["shared"])                # 個人から戻す


def test_renamed_in_shared_is_same_note(box):
    run_once(box["yu"])
    sh = box["shared"]
    (sh / "共通/02_ノード/0RB001001_水.md").rename(sh / "共通/02_ノード/0RB001001_みず.md")
    run_once(box["yu"])
    assert "同じ id" not in report(box["yu"])
    s = files(sh)
    assert "共通/02_ノード/0RB001001_水.md" in s and "共通/02_ノード/0RB001001_みず.md" not in s
