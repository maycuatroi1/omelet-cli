from __future__ import annotations

import re

import mistune

from .jsx_tokenizer import (
    JsxNode,
    JsxParseError,
    parse_component_at,
)


CITE_SHORTHAND_RE = re.compile(r"\[@([A-Za-z0-9][A-Za-z0-9_.-]*)\]")
JSX_BLOCK_START = re.compile(r"^<[A-Z][A-Za-z0-9]*[\s/>]", re.MULTILINE)


def _parse_jsx_block(block, m, state):
    source = state.src
    start = m.start()
    try:
        node = parse_component_at(source, start)
    except JsxParseError as e:
        raise mistune.directives.DirectiveParseError(str(e)) from e
    if node is None:
        return None

    state.append_token({
        "type": "jsx_component",
        "raw": source[node.start:node.end],
        "attrs": {
            "name": node.name,
            "props": node.props,
            "self_closing": node.self_closing,
            "children_raw": node.children_raw,
        },
    })
    end = node.end
    while end < len(source) and source[end] in " \t":
        end += 1
    if end < len(source) and source[end] == "\n":
        end += 1
    return end


def jsx_block_plugin(md: mistune.Markdown) -> None:
    md.block.register(
        "jsx_block",
        r"^<[A-Z][A-Za-z0-9]*(?:\s|/|>)",
        _parse_jsx_block,
        before="raw_html",
    )


def _parse_jsx_inline(inline, m, state):
    source = state.src
    start = m.start()
    try:
        node = parse_component_at(source, start)
    except JsxParseError:
        return None
    if node is None:
        return None
    state.append_token({
        "type": "jsx_inline",
        "raw": source[node.start:node.end],
        "attrs": {
            "name": node.name,
            "props": node.props,
            "self_closing": node.self_closing,
            "children_raw": node.children_raw,
        },
    })
    return node.end


def jsx_inline_plugin(md: mistune.Markdown) -> None:
    md.inline.register(
        "jsx_inline",
        r"<[A-Z][A-Za-z0-9]*(?:\s|/|>)",
        _parse_jsx_inline,
        before="inline_html",
    )


def _parse_cite_shorthand(inline, m, state):
    key = m.group("cite_key")
    state.append_token({
        "type": "jsx_inline",
        "raw": m.group(0),
        "attrs": {
            "name": "Cite",
            "props": {"key": key},
            "self_closing": True,
            "children_raw": "",
        },
    })
    return m.end()


def cite_shorthand_plugin(md: mistune.Markdown) -> None:
    md.inline.register(
        "cite_shorthand",
        r"\[@(?P<cite_key>[A-Za-z0-9][A-Za-z0-9_.-]*)\]",
        _parse_cite_shorthand,
        before="link",
    )


def _parse_math_block(block, m, state):
    content = m.group("math_block_content")
    state.append_token({
        "type": "math_block",
        "raw": content,
    })
    return m.end()


def math_block_plugin(md: mistune.Markdown) -> None:
    md.block.register(
        "math_block",
        r"^\$\$[^\S\n]*\n?(?P<math_block_content>[\s\S]+?)\n?\$\$[^\S\n]*$",
        _parse_math_block,
        before="paragraph",
    )


def _parse_math_inline(inline, m, state):
    content = m.group("math_inline_content")
    state.append_token({
        "type": "math_inline",
        "raw": content,
    })
    return m.end()


def math_inline_plugin(md: mistune.Markdown) -> None:
    md.inline.register(
        "math_inline",
        r"(?<!\\)\$(?P<math_inline_content>(?:\\.|[^\$\n])+?)(?<!\\)\$",
        _parse_math_inline,
        before="emphasis",
    )


def make_parser() -> mistune.Markdown:
    md = mistune.create_markdown(
        renderer=None,
        plugins=[
            jsx_block_plugin,
            jsx_inline_plugin,
            cite_shorthand_plugin,
            math_block_plugin,
            math_inline_plugin,
            "table",
            "strikethrough",
            "footnotes",
            "url",
        ],
    )
    return md
