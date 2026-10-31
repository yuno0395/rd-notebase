"""機密の窓口: secret_refs は共有の 共通/機密の窓口/ のノートへのリンクにする。名前が漏れていれば集めない。"""

from .test_share import PJ, cloud, files, report, write  # noqa: F401


def window(c, name="案件A", body=""):
    return write(c.personal / f"02_ノード/0RB900001_{name}.md",
                 f"---\nid: 0RB900001\ntype: 窓口\nreaders: [Yu, 佐藤]\nowner: [Yu]\n---\n{body}")


def issue_with_refs(c, refs):
    return write(c.personal / "03_イシュー/0RB901001_荷重.md",
                 f"---\nid: 0RB901001\ntype: イシュー\nproject: [{PJ}]\nsecret_refs: {refs}\n---\n要求荷重 500N\n")


def test_window_goes_to_common_and_refs_are_fine(cloud):
    yu = cloud["yu"]
    window(yu)
    issue_with_refs(yu, '["[[0RB900001_案件A|案件A]]"]')
    run_once_twice(cloud)
    s = files(cloud["shared"])
    assert "共通/機密の窓口/0RB900001_案件A.md" in s
    assert f"{PJ}/03_イシュー/0RB901001_荷重.md" in s
    assert "機密の窓口へのリンクではありません" not in report(yu)
    # 佐藤にも配られる
    assert "90_共有/共通/機密の窓口/0RB900001_案件A.md" in files(cloud["sato"].personal)


def test_window_with_secret_folder_name_is_not_shared(cloud):
    yu = cloud["yu"]
    window(yu, body="機密_顧客A の窓口\n")
    from notesync.run import run_once
    run_once(yu)
    assert "共通/機密の窓口/0RB900001_案件A.md" not in files(cloud["shared"])
    assert "機密フォルダか事実ノートの名前(機密_顧客a)" in report(yu)


def test_refs_with_fact_name_are_not_shared(cloud):
    yu = cloud["yu"]
    issue_with_refs(yu, '["顧客図面"]')
    from notesync.run import run_once
    run_once(yu)
    assert f"{PJ}/03_イシュー/0RB901001_荷重.md" not in files(cloud["shared"])
    assert "secret_refs に、機密フォルダか事実ノートの名前(顧客図面)" in report(yu)


def test_old_id_form_is_shared_with_notice(cloud):
    yu = cloud["yu"]
    issue_with_refs(yu, '["0RC001001"]')
    from notesync.run import run_once
    run_once(yu)
    assert f"{PJ}/03_イシュー/0RB901001_荷重.md" in files(cloud["shared"])
    assert "0RC001001 は機密の窓口へのリンクではありません" in report(yu)


def run_once_twice(cloud):
    from notesync.run import run_once
    run_once(cloud["yu"])
    run_once(cloud["sato"])
