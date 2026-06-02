from pathlib import Path

import pytest

from omelet.mdx.compiler import compile_mdx_string
from omelet.mdx.components import ComponentError
from omelet.mdx.sanitize import is_invariant


def compile_with(src: str, citations_yaml: Path) -> str:
    r = compile_mdx_string(
        src,
        citations_path=citations_yaml,
        assets_dir=citations_yaml.parent,
    )
    return r.body_html


class TestEvidence:
    def test_basic(self, citations_yaml):
        html = compile_with(
            '<Evidence claim="X" confidence="high">'
            '<Source url="https://x.com">body</Source>'
            "</Evidence>",
            citations_yaml,
        )
        assert "omelet-evidence--high" in html
        assert "X" in html
        assert "https://x.com" in html

    def test_default_confidence(self, citations_yaml):
        html = compile_with(
            '<Evidence claim="X"><Source url="https://x.com">b</Source></Evidence>',
            citations_yaml,
        )
        assert "omelet-evidence--medium" in html

    def test_invalid_confidence_falls_back(self, citations_yaml):
        html = compile_with(
            '<Evidence claim="X" confidence="weird"><Source url="https://x.com">b</Source></Evidence>',
            citations_yaml,
        )
        assert "omelet-evidence--medium" in html

    def test_missing_claim_raises(self, citations_yaml):
        with pytest.raises(ComponentError, match="claim"):
            compile_with(
                '<Evidence confidence="high"><Source url="https://x.com">b</Source></Evidence>',
                citations_yaml,
            )


class TestScenario:
    def test_basic(self, citations_yaml):
        html = compile_with(
            '<Scenario title="Soft" probability="35-45" trigger="Fed cut" timeline="Q2">body</Scenario>',
            citations_yaml,
        )
        assert "Soft" in html
        assert "35–45%" in html

    def test_single_probability(self, citations_yaml):
        html = compile_with(
            '<Scenario title="X" probability="50" trigger="t">body</Scenario>',
            citations_yaml,
        )
        assert "50%" in html

    def test_invalid_probability_raises(self, citations_yaml):
        with pytest.raises(ComponentError, match="probability"):
            compile_with(
                '<Scenario title="X" probability="high" trigger="t">body</Scenario>',
                citations_yaml,
            )


class TestObjection:
    def test_basic(self, citations_yaml):
        html = compile_with(
            '<Objection claim="Counter" strength="strong">Rebuttal text.</Objection>',
            citations_yaml,
        )
        assert "Counter" in html
        assert "Rebuttal text" in html
        assert "omelet-objection--strong" in html

    def test_empty_rebuttal_raises(self, citations_yaml):
        with pytest.raises(ComponentError, match="rebuttal"):
            compile_with(
                '<Objection claim="X" strength="strong"></Objection>',
                citations_yaml,
            )


class TestAnalogy:
    def test_basic(self, citations_yaml):
        src = (
            '<Analogy title="Bowls">'
            "<Everyday>Two bowls.</Everyday>"
            "<Technical>Two SGLs.</Technical>"
            "</Analogy>"
        )
        html = compile_with(src, citations_yaml)
        assert "Bowls" in html
        assert "Two bowls" in html
        assert "Two SGLs" in html

    def test_optional_implication(self, citations_yaml):
        src = (
            '<Analogy title="X">'
            "<Everyday>e</Everyday>"
            "<Technical>t</Technical>"
            "<Implication>i</Implication>"
            "</Analogy>"
        )
        html = compile_with(src, citations_yaml)
        assert "Hệ quả" in html

    def test_missing_required_slot(self, citations_yaml):
        with pytest.raises(ComponentError, match="Everyday"):
            compile_with(
                '<Analogy title="X"><Technical>t</Technical></Analogy>',
                citations_yaml,
            )

    def test_unknown_slot(self, citations_yaml):
        with pytest.raises(ComponentError, match="Foo"):
            compile_with(
                '<Analogy title="X"><Everyday>e</Everyday><Technical>t</Technical><Foo>f</Foo></Analogy>',
                citations_yaml,
            )


class TestCite:
    def test_inline_shorthand(self, citations_yaml):
        html = compile_with("Some [@khosla2025] cite.", citations_yaml)
        assert "[1]" in html
        assert "#cite-khosla2025" in html

    def test_jsx_form(self, citations_yaml):
        html = compile_with('Some <Cite key="khosla2025" /> cite.', citations_yaml)
        assert "[1]" in html

    def test_unknown_key_raises(self, citations_yaml):
        from omelet.mdx.citations import CitationError
        with pytest.raises(CitationError, match="Unknown"):
            compile_with("[@nonexistent2099]", citations_yaml)

    def test_repeat_key_same_number(self, citations_yaml):
        html = compile_with("[@khosla2025] then [@khosla2025] again.", citations_yaml)
        assert html.count("[1]") == 2


class TestSanitization:
    def test_full_post_invariant(self, citations_yaml):
        src = (
            "# Hello\n\n"
            'Para with [@khosla2025].\n\n'
            '<Evidence claim="X" confidence="high">'
            '<Source url="https://x.com" date="2025-Q3" type="sec-filing">**Body**.</Source>'
            "</Evidence>\n\n"
            '<Scenario title="S" probability="35-45" trigger="t" timeline="x">**bold**</Scenario>\n\n'
            '<Objection claim="C" strength="strong">Rebut [@amodei-2026].</Objection>\n\n'
            '<Analogy title="A"><Everyday>e</Everyday><Technical>t</Technical></Analogy>\n'
        )
        r = compile_mdx_string(
            src, citations_path=citations_yaml, assets_dir=citations_yaml.parent,
        )
        assert is_invariant(r.html), (
            f"Sanitized output differs from raw — Ghost will strip something. "
            f"Raw len={len(r.html)} sanitized len={len(__import__('omelet.mdx.sanitize', fromlist=['sanitize']).sanitize(r.html))}"
        )
