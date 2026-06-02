import pytest

from omelet.mdx.jsx_tokenizer import (
    JsxParseError,
    find_next_component,
    parse_component_at,
)


class TestParseComponent:
    def test_self_closing(self):
        n = parse_component_at('<Cite key="khosla2025" />', 0)
        assert n.name == "Cite"
        assert n.props == {"key": "khosla2025"}
        assert n.self_closing

    def test_block_with_children(self):
        src = '<Evidence claim="X">body</Evidence>'
        n = parse_component_at(src, 0)
        assert n.name == "Evidence"
        assert n.children_raw == "body"
        assert not n.self_closing

    def test_expr_attr_list(self):
        n = parse_component_at("<Scenario probability={[35, 45]}>x</Scenario>", 0)
        assert n.props == {"probability": [35, 45]}

    def test_expr_attr_dict(self):
        n = parse_component_at('<X data={{"k": 1}}>y</X>', 0)
        assert n.props == {"data": {"k": 1}}

    def test_nested_same_name(self):
        n = parse_component_at("<Outer><Outer>nested</Outer></Outer>", 0)
        assert n.children_raw == "<Outer>nested</Outer>"

    def test_skips_code_fence(self):
        n = parse_component_at("<Box> ` </Box> ` </Box>", 0)
        assert n.name == "Box"
        assert "` </Box> `" in n.children_raw

    def test_unclosed_raises(self):
        with pytest.raises(JsxParseError):
            parse_component_at("<X>unclosed", 0)

    def test_mismatched_close_raises(self):
        with pytest.raises(JsxParseError):
            parse_component_at("<X>err</Y>", 0)

    def test_boolean_attr(self):
        n = parse_component_at("<X disabled />", 0)
        assert n.props == {"disabled": True}


class TestFindNextComponent:
    def test_finds_block(self):
        assert find_next_component("text <Foo/> rest") == (5, "Foo")

    def test_skips_inline_code(self):
        assert find_next_component("text `<Foo/>` rest") is None

    def test_skips_fenced_code(self):
        assert find_next_component("text ```\n<Foo/>\n``` rest") is None

    def test_lowercase_not_component(self):
        assert find_next_component("<div>not a component</div>") is None

    def test_returns_none_when_absent(self):
        assert find_next_component("plain text") is None
