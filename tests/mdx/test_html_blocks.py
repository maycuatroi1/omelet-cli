from pathlib import Path

import pytest

from omelet.mdx.compiler import compile_mdx_string
from omelet.mdx.components import ComponentError
from omelet.mdx.sanitize import SanitizeError, is_invariant, sanitize


BEGIN = "<!--kg-card-begin: html-->"
END = "<!--kg-card-end: html-->"
SENTINEL = "<!--omelet:widget-->"

CANVAS = (
    '<div class="tokenizer">'
    '<canvas id="tokenizer-canvas" width="640" height="240"></canvas>'
    "</div>"
)

SVG = (
    '<svg viewBox="0 0 200 40" role="img" aria-label="Sơ đồ khối">'
    '<rect x="1" y="1" width="40" height="20" fill="none" stroke="currentColor"/>'
    '<text x="6" y="14" font-size="7" fill="currentColor">KDA</text>'
    '<path d="M41 11 L60 11" stroke="currentColor"/>'
    "</svg>"
)


def compile_with(src: str, citations_yaml: Path) -> str:
    r = compile_mdx_string(
        src,
        citations_path=citations_yaml,
        assets_dir=citations_yaml.parent,
    )
    return r.body_html


class TestVerbatimBlocks:
    def test_svg_survives_inside_markers(self):
        html = sanitize(f"<p>a</p>\n{BEGIN}\n{SVG}\n{END}\n")
        assert "<path" in html
        assert 'viewBox="0 0 200 40"' in html

    def test_style_attribute_survives_inside_markers(self):
        html = sanitize(f'{BEGIN}<div style="display:grid">x</div>{END}')
        assert 'style="display:grid"' in html

    def test_style_attribute_still_stripped_outside(self):
        html = sanitize('<div style="display:grid">x</div>')
        assert "style" not in html

    def test_ordinary_comment_still_stripped_outside(self):
        assert sanitize("<p>a</p><!-- note -->") == "<p>a</p>"

    def test_markers_themselves_survive(self):
        html = sanitize(f"{BEGIN}<div>x</div>{END}")
        assert html.startswith(BEGIN)
        assert html.endswith(END)

    def test_only_the_marked_block_is_verbatim(self):
        html = sanitize(f'{BEGIN}<div style="a">x</div>{END}<div style="b">y</div>')
        assert 'style="a"' in html
        assert 'style="b"' not in html


class TestVerbatimGuards:
    @pytest.mark.parametrize(
        "body",
        [
            "<div><script>alert(1)</script></div>",
            '<svg onload="boom()"></svg>',
            '<a href="javascript:boom()">x</a>',
        ],
    )
    def test_executable_markup_fails_the_build(self, body):
        with pytest.raises(SanitizeError, match="executable markup"):
            sanitize(f"{BEGIN}{body}{END}")

    def test_prose_that_merely_looks_like_a_handler_is_fine(self):
        html = sanitize(f"{BEGIN}<svg><text>che do on = 1</text></svg>{END}")
        assert "on = 1" in html

    def test_svg_outside_a_card_names_the_fix(self):
        with pytest.raises(SanitizeError, match="Diagram"):
            sanitize(f"<p>a</p>{SVG}")

    def test_unclosed_marker_does_not_silently_pass_the_rest(self):
        with pytest.raises(SanitizeError, match="never closed"):
            sanitize(f"{BEGIN}<div>x</div>")

    def test_end_marker_alone_is_an_error(self):
        with pytest.raises(SanitizeError, match="no matching"):
            sanitize(f"<p>a</p>{END}")

    def test_nested_begin_is_an_error(self):
        with pytest.raises(SanitizeError, match="opened twice"):
            sanitize(f"{BEGIN}{BEGIN}<div>x</div>{END}")


class TestDiagram:
    def test_wraps_children_in_a_card(self, citations_yaml):
        html = compile_with(f"<Diagram>\n{SVG}\n</Diagram>", citations_yaml)
        assert BEGIN in html and END in html
        assert SVG in html
        assert 'class="omelet-diagram"' in html

    def test_output_passes_sanitize_untouched(self, citations_yaml):
        html = compile_with(
            f'<Diagram caption="Hình 1">\n{SVG}\n</Diagram>', citations_yaml
        )
        assert is_invariant(html)

    def test_caption_renders_inline_markdown_without_a_paragraph(self, citations_yaml):
        html = compile_with(
            f'<Diagram caption="Hình 1. `KDA` và **MLA**">\n{SVG}\n</Diagram>',
            citations_yaml,
        )
        assert "<code>KDA</code>" in html
        assert "<strong>MLA</strong>" in html
        assert "<figcaption" in html
        assert "<p>" not in html

    def test_no_caption_means_no_figcaption(self, citations_yaml):
        html = compile_with(f"<Diagram>\n{SVG}\n</Diagram>", citations_yaml)
        assert "figcaption" not in html

    def test_extra_class_is_appended(self, citations_yaml):
        html = compile_with(
            f'<Diagram class="wide">\n{SVG}\n</Diagram>', citations_yaml
        )
        assert 'class="omelet-diagram wide"' in html

    def test_children_are_not_parsed_as_markdown(self, citations_yaml):
        html = compile_with(
            "<Diagram>\n<div>\n\n*not emphasis*\n\n</div>\n</Diagram>", citations_yaml
        )
        assert "*not emphasis*" in html
        assert "<em>" not in html

    def test_empty_diagram_is_an_error(self, citations_yaml):
        with pytest.raises(ComponentError, match="empty"):
            compile_with("<Diagram>\n \n</Diagram>", citations_yaml)

    def test_markdown_image_child_is_an_error(self, citations_yaml):
        with pytest.raises(ComponentError, match="raw markup"):
            compile_with("<Diagram>\n![a](./b.svg)\n</Diagram>", citations_yaml)


class TestDiagramSrc:
    def test_inlines_the_file(self, citations_yaml):
        (citations_yaml.parent / "d.svg").write_text(SVG, encoding="utf-8")
        html = compile_with('<Diagram src="./d.svg" />', citations_yaml)
        assert SVG in html
        assert BEGIN in html and END in html

    def test_xml_prolog_is_dropped(self, citations_yaml):
        (citations_yaml.parent / "p.svg").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n' + SVG, encoding="utf-8"
        )
        html = compile_with('<Diagram src="./p.svg" />', citations_yaml)
        assert "<?xml" not in html
        assert html.count("<svg") == 1

    def test_missing_file_names_the_path(self, citations_yaml):
        with pytest.raises(ComponentError, match="not found"):
            compile_with('<Diagram src="./nope.svg" />', citations_yaml)

    def test_wrong_suffix_is_rejected(self, citations_yaml):
        (citations_yaml.parent / "d.png").write_bytes(b"\x89PNG")
        with pytest.raises(ComponentError, match="must point at"):
            compile_with('<Diagram src="./d.png" />', citations_yaml)

    def test_src_and_children_together_is_an_error(self, citations_yaml):
        (citations_yaml.parent / "d.svg").write_text(SVG, encoding="utf-8")
        with pytest.raises(ComponentError, match="not both"):
            compile_with(f'<Diagram src="./d.svg">\n{SVG}\n</Diagram>', citations_yaml)

    def test_caption_still_works(self, citations_yaml):
        (citations_yaml.parent / "d.svg").write_text(SVG, encoding="utf-8")
        html = compile_with(
            '<Diagram src="./d.svg" caption="Hình 2. Hai trục" />', citations_yaml
        )
        assert "Hình 2. Hai trục" in html
        assert is_invariant(html)


class TestWidget:
    def test_missing_src_is_an_error(self, citations_yaml):
        with pytest.raises(ComponentError, match="missing required prop"):
            compile_with("<Widget />", citations_yaml)

    def test_wrong_suffix_is_rejected(self, citations_yaml):
        (citations_yaml.parent / "w.svg").write_text(SVG, encoding="utf-8")
        with pytest.raises(ComponentError, match="must point at"):
            compile_with('<Widget src="./w.svg" />', citations_yaml)

    def test_missing_file_names_the_path(self, citations_yaml):
        with pytest.raises(ComponentError, match="not found"):
            compile_with('<Widget src="./nope.html" />', citations_yaml)

    def test_canvas_file_becomes_a_figure(self, citations_yaml):
        (citations_yaml.parent / "w.html").write_text(CANVAS, encoding="utf-8")
        html = compile_with('<Widget src="./w.html" />', citations_yaml)
        assert 'class="omelet-widget"' in html
        assert "<canvas" in html
        assert 'id="tokenizer-canvas"' in html

    def test_sentinel_sits_right_after_the_begin_marker(self, citations_yaml):
        (citations_yaml.parent / "w.html").write_text(CANVAS, encoding="utf-8")
        html = compile_with('<Widget src="./w.html" />', citations_yaml)
        assert BEGIN in html and END in html
        assert f"{BEGIN}\n{SENTINEL}" in html

    def test_caption_and_extra_class(self, citations_yaml):
        (citations_yaml.parent / "w.html").write_text(CANVAS, encoding="utf-8")
        html = compile_with(
            '<Widget src="./w.html" class="wide" caption="Hình 3. `BPE` chạy thật" />',
            citations_yaml,
        )
        assert 'class="omelet-widget wide"' in html
        assert '<figcaption class="omelet-widget__caption">' in html
        assert "<code>BPE</code>" in html
        assert "Hình 3." in html

    def test_script_in_the_file_survives_sanitize(self, citations_yaml):
        (citations_yaml.parent / "w.html").write_text(
            CANVAS + '\n<script>document.title = "x";</script>', encoding="utf-8"
        )
        html = compile_with('<Widget src="./w.html" />', citations_yaml)
        cleaned = sanitize(html)
        assert "<script>" in cleaned
        assert 'document.title = "x";' in cleaned
        assert is_invariant(html)

    def test_a_plain_card_next_to_a_widget_still_rejects_script(self, citations_yaml):
        (citations_yaml.parent / "w.html").write_text(
            CANVAS + "\n<script>void 0;</script>", encoding="utf-8"
        )
        html = compile_with('<Widget src="./w.html" />', citations_yaml)
        with pytest.raises(SanitizeError, match="executable markup"):
            sanitize(html + f"{BEGIN}<div><script>alert(1)</script></div>{END}")

    def test_doctype_is_dropped(self, citations_yaml):
        (citations_yaml.parent / "w.html").write_text(
            "<!DOCTYPE html>\n" + CANVAS, encoding="utf-8"
        )
        html = compile_with('<Widget src="./w.html" />', citations_yaml)
        assert "DOCTYPE" not in html
