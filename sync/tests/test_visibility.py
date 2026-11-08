"""visibility の値(v0.91)。"""

from notesync import visibility as vis

PJS = {"試しPJ", "別PJ"}
EXT = {"EXT_協力工場A"}


def p(v):
    return vis.problems({"visibility": v}, PJS, EXT)


def test_allowed():
    assert p(["PIP"]) == []
    assert p(["Internal use only"]) == []
    assert p(["Internal use only", "EXT_協力工場A"]) == []
    assert p(["試しPJ", "別PJ", "EXT_協力工場A"]) == []
    assert p("試しPJ") == []                       # 1つだけ書いたもの
    assert p(None) == [] and p("チーム") == []     # v0.89 までの書き方・空
    assert p("個人") == [] and p("社内") == []


def test_rejected():
    assert p(["PIP", "試しPJ"]) and p(["PIP", "EXT_協力工場A"])
    assert p(["Internal use only", "試しPJ"])
    assert p(["チームA"]) and p(["EXT_知らない"])
    assert p(["試しPJ", "試しPJ"])


def test_is_pip_and_visible_in():
    assert vis.is_pip({"visibility": ["PIP"]}) and vis.is_pip({"visibility": "個人"}) and vis.is_pip({"type": "メモ"})
    assert not vis.is_pip({"visibility": ["試しPJ"]})
    assert vis.visible_in({"visibility": ["試しPJ"]}, "試しPJ")
    assert not vis.visible_in({"visibility": ["試しPJ"]}, "別PJ")
    assert vis.visible_in({"visibility": ["Internal use only"]}, "別PJ")
    assert vis.visible_in({}, "別PJ")
    assert not vis.visible_in({"visibility": "個人"}, None)


def test_read_ext(tmp_path):
    (tmp_path / "_仕組み").mkdir()
    (tmp_path / "_仕組み/EXT_一覧.csv").write_text("名前,社内の担当\nEXT_協力工場A,山田\n商社B,山田\n", encoding="utf-8")
    assert vis.read_ext(tmp_path) == {"EXT_協力工場A", "EXT_商社B"}
    assert vis.read_ext(tmp_path / "無い") == set()
