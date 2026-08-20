from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mistune import HTMLRenderer

from . import components as components_mod
from .citations import CiteRegistry, load_citations, render_bibliography
from .components import ComponentError, RenderContext
from .parser import make_parser


@dataclass
class CompileResult:
    frontmatter: dict
    html: str
    body_html: str
    bibliography_html: str
    used_citations: list[str]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    from omelet.ghost_client import parse_frontmatter as _pf
    return _pf(content)


def _render_tokens(tokens, ctx: RenderContext, html_renderer: HTMLRenderer) -> str:
    out: list[str] = []
    for tok in tokens:
        out.append(_render_token(tok, ctx, html_renderer))
    return "".join(out)


def _render_token(token, ctx: RenderContext, html_renderer: HTMLRenderer) -> str:
    typ = token.get("type")
    if typ == "jsx_component" or typ == "jsx_inline":
        attrs = token["attrs"]
        return _render_component(attrs, ctx)
    return _render_markdown_token(token, ctx, html_renderer)


def _render_markdown_token(token, ctx: RenderContext, html_renderer: HTMLRenderer) -> str:
    children = token.get("children")
    if isinstance(children, list):
        for child in children:
            if child.get("type") in ("jsx_component", "jsx_inline"):
                child["__rendered_html__"] = _render_component(child["attrs"], ctx)
    state = type("S", (), {"env": {}})()
    return _walk_render(token, ctx, html_renderer, state)


def _walk_render(token, ctx: RenderContext, html_renderer: HTMLRenderer, state) -> str:
    typ = token.get("type")
    if typ in ("jsx_component", "jsx_inline"):
        if "__rendered_html__" in token:
            return token["__rendered_html__"]
        return _render_component(token["attrs"], ctx)

    children = token.get("children")
    if isinstance(children, list):
        children_html = "".join(_walk_render(c, ctx, html_renderer, state) for c in children)
    else:
        children_html = token.get("raw", "") or ""

    try:
        method = html_renderer._get_method(typ)
    except AttributeError:
        return children_html

    attrs = token.get("attrs") or {}
    has_children_or_raw = isinstance(children, list) or "raw" in token
    try:
        if has_children_or_raw:
            return method(children_html, **attrs)
        return method(**attrs)
    except TypeError:
        try:
            return method(children_html)
        except TypeError:
            return children_html


def _render_component(attrs: dict, ctx: RenderContext) -> str:
    name = attrs["name"]
    props = dict(attrs["props"])
    children_raw = attrs.get("children_raw", "")
    self_closing = attrs.get("self_closing", False)

    fn = components_mod.get(name)
    if fn is None:
        if ctx.components_strict:
            raise ComponentError(f"Unknown component <{name}>")
        return f"<!-- unknown component: {name} -->"

    # Pushed before the children render, not after: a nested component asks
    # parent_chain whether anything already wraps it, and that answer has to be
    # true while it is still being built.
    ctx.parent_chain.append(name)
    try:
        children_html = ""
        if not self_closing and children_raw:
            if getattr(fn, "raw_children", False):
                props["__children_raw__"] = children_raw
            else:
                children_html = _render_children(children_raw, ctx, name)
        return fn(ctx, props, children_html)
    finally:
        ctx.parent_chain.pop()


def _render_children(children_raw: str, ctx: RenderContext, parent_name: str) -> str:
    import textwrap
    dedented = textwrap.dedent(children_raw).strip("\n")
    md = make_parser()
    tokens, _ = md.parse(dedented)
    html_renderer = _make_html_renderer()
    return _render_tokens(tokens, ctx, html_renderer)


def _make_html_renderer() -> HTMLRenderer:
    renderer = HTMLRenderer(escape=False, allow_harmful_protocols=False)
    _register_plugin_renderers(renderer)
    return renderer


def _register_plugin_renderers(renderer: HTMLRenderer) -> None:
    from mistune.plugins.table import (
        render_table,
        render_table_body,
        render_table_cell,
        render_table_head,
        render_table_row,
    )
    from mistune.plugins.formatting import render_strikethrough
    from mistune.plugins.footnotes import (
        render_footnote_ref,
        render_footnote_item,
        render_footnotes,
    )

    renderer.register("table", render_table)
    renderer.register("table_head", render_table_head)
    renderer.register("table_body", render_table_body)
    renderer.register("table_row", render_table_row)
    renderer.register("table_cell", render_table_cell)
    renderer.register("strikethrough", render_strikethrough)
    renderer.register("footnote_ref", render_footnote_ref)
    renderer.register("footnote_item", render_footnote_item)
    renderer.register("footnotes", render_footnotes)
    renderer.register("math_inline", _render_math_inline)
    renderer.register("math_block", _render_math_block)


def _render_math_inline(_renderer, content: str) -> str:
    return f'<span class="omelet-math math-inline">\\({content}\\)</span>'


def _render_math_block(_renderer, content: str) -> str:
    return f'<div class="omelet-math math-display">\\[{content}\\]</div>\n'


def compile_mdx_string(
    source: str,
    *,
    citations_path: Optional[Path] = None,
    assets_dir: Optional[Path] = None,
    slug: str = "",
    strict: Optional[bool] = None,
    bibliography_heading: Optional[str] = None,
) -> CompileResult:
    frontmatter, body = parse_frontmatter(source)

    if citations_path is None:
        cite_path_str = frontmatter.get("citations")
        if cite_path_str and assets_dir:
            citations_path = (assets_dir / cite_path_str).resolve()

    citations = load_citations(citations_path) if citations_path else CiteRegistry()

    if strict is None:
        fm_strict = frontmatter.get("components_strict", True)
        if isinstance(fm_strict, str):
            strict = fm_strict.lower() not in ("false", "no", "0")
        else:
            strict = bool(fm_strict)

    if bibliography_heading is None:
        bibliography_heading = str(
            frontmatter.get("bibliography_heading", "Phụ lục: Citations")
        )

    md = make_parser()
    tokens, _ = md.parse(body)
    html_renderer = _make_html_renderer()

    def md_render(text: str) -> str:
        sub_tokens, _ = make_parser().parse(text)
        return _render_tokens(sub_tokens, ctx, _make_html_renderer())

    ctx = RenderContext(
        citations=citations,
        frontmatter=frontmatter,
        assets_dir=assets_dir,
        slug=slug,
        components_strict=strict,
        md_renderer=None,
    )
    ctx.md_renderer = md_render

    body_html = _render_tokens(tokens, ctx, html_renderer)
    bibliography_html = render_bibliography(citations, heading=bibliography_heading)
    full_html = body_html + ("\n" + bibliography_html if bibliography_html else "")
    return CompileResult(
        frontmatter=frontmatter,
        html=full_html,
        body_html=body_html,
        bibliography_html=bibliography_html,
        used_citations=citations.used_keys(),
    )


def compile_mdx_path(path) -> CompileResult:
    p = Path(path)
    source = p.read_text(encoding="utf-8")
    citations_default = p.parent / "citations.yaml"
    citations_path = citations_default if citations_default.exists() else None
    return compile_mdx_string(
        source,
        citations_path=citations_path,
        assets_dir=p.parent,
        slug=p.parent.name,
    )
