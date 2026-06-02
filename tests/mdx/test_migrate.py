from pathlib import Path

from omelet.mdx.migrate import (
    auto_key,
    extract_footnotes,
    parse_keymap,
    rewrite_footnotes,
)


def test_extract_footnotes_basic():
    md = (
        "Body with [^1^] and [^2^].\n\n"
        "## Phụ lục: Citations\n\n"
        "[^1^]: First note https://example.com/foo 2025\n"
        "[^2^]: Second note https://other.com 2024\n"
    )
    notes = extract_footnotes(md)
    assert "1" in notes
    assert notes["1"]["url"] == "https://example.com/foo"


def test_auto_key_uses_host_and_year():
    used: set = set()
    key = auto_key("1", "Article body 2025", "https://fortune.com/article", used)
    assert key == "fortune-2025"


def test_auto_key_collision():
    used = {"fortune-2025"}
    key = auto_key("2", "another 2025", "https://fortune.com/x", used)
    assert key == "fortune-2025-2"


def test_rewrite_footnotes_basic():
    md = (
        "Body [^1^] and [^2^].\n\n"
        "## Phụ lục: Citations\n\n"
        "[^1^]: One\n"
        "[^2^]: Two\n"
    )
    keymap = {"1": "khosla-2025", "2": "amodei-2026"}
    out = rewrite_footnotes(md, keymap)
    assert "[@khosla-2025]" in out
    assert "[@amodei-2026]" in out
    assert "[^1^]" not in out
    assert "Phụ lục" not in out


def test_rewrite_preserves_content_after_appendix():
    md = (
        "Body [^1^].\n\n"
        "## Phụ lục: Citations\n\n"
        "[^1^]: One\n\n"
        "## Aftermath\n\n"
        "Important content here.\n"
    )
    out = rewrite_footnotes(md, {"1": "k1"})
    assert "Aftermath" in out
    assert "Important content here." in out


def test_parse_keymap(tmp_path: Path):
    p = tmp_path / "key_map.txt"
    p.write_text("[^1^] -> foo-2025\n[^13^] -> amodei-2026\n# comment\n")
    m = parse_keymap(p)
    assert m == {"1": "foo-2025", "13": "amodei-2026"}
