from notesync import frontmatter


def test_keeps_other_lines_and_comments():
    src = "---\ntype: ノード   # 物のノード\naliases: [氷, こおり]\n---\n本文\n"
    out = frontmatter.set_values(src, {"id": "0RDGPG001", "author": "Yu"})
    assert out == "---\nid: 0RDGPG001\nauthor: Yu\ntype: ノード   # 物のノード\naliases: [氷, こおり]\n---\n本文\n"


def test_replaces_existing_key():
    src = "---\nid: OLD\ntype: x\n---\n"
    assert frontmatter.set_values(src, {"id": "NEW"}) == "---\nid: NEW\ntype: x\n---\n"


def test_creates_frontmatter_and_keeps_crlf():
    assert frontmatter.set_values("本文\r\n", {"id": "A"}) == "---\r\nid: A\r\n---\r\n本文\r\n"
    src = "---\r\ntype: x\r\n---\r\n本文\r\n"
    assert frontmatter.set_values(src, {"id": "A"}) == "---\r\nid: A\r\ntype: x\r\n---\r\n本文\r\n"


def test_load():
    assert frontmatter.load("---\nid: 0RDGPG001\naliases: [a, b]\n---\n") == {"id": "0RDGPG001", "aliases": ["a", "b"]}
    assert frontmatter.load("本文だけ") == {}
    assert frontmatter.load("---\n: : 壊れた\n---\n") == {}
