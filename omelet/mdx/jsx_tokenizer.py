from __future__ import annotations

import ast as py_ast
import re
from dataclasses import dataclass, field
from typing import Optional


COMPONENT_NAME_RE = re.compile(r"[A-Z][A-Za-z0-9]*")
ATTR_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
WS_RE = re.compile(r"\s+")


class JsxParseError(Exception):
    def __init__(self, message: str, pos: int, source: str) -> None:
        line = source.count("\n", 0, pos) + 1
        col = pos - (source.rfind("\n", 0, pos) + 1) + 1
        super().__init__(f"{message} (line {line}, col {col})")
        self.line = line
        self.col = col
        self.pos = pos


@dataclass
class JsxNode:
    name: str
    props: dict = field(default_factory=dict)
    children_raw: str = ""
    self_closing: bool = False
    start: int = 0
    end: int = 0


def parse_component_at(source: str, start: int) -> Optional[JsxNode]:
    if start >= len(source) or source[start] != "<":
        return None
    pos = start + 1
    m = COMPONENT_NAME_RE.match(source, pos)
    if not m:
        return None
    name = m.group(0)
    pos = m.end()

    props, pos = _parse_props(source, pos)

    pos = _skip_ws(source, pos)
    if pos >= len(source):
        raise JsxParseError(f"Unexpected EOF in <{name}>", pos, source)

    if source[pos:pos + 2] == "/>":
        return JsxNode(
            name=name, props=props, children_raw="",
            self_closing=True, start=start, end=pos + 2,
        )

    if source[pos] != ">":
        raise JsxParseError(
            f"Expected '>' or '/>' in <{name}>, got {source[pos]!r}", pos, source,
        )
    pos += 1

    children_start = pos
    close_pos = _find_matching_close(source, pos, name)
    children_raw = source[children_start:close_pos]
    end = close_pos + len(f"</{name}>")
    return JsxNode(
        name=name, props=props, children_raw=children_raw,
        self_closing=False, start=start, end=end,
    )


def _parse_props(source: str, pos: int) -> tuple[dict, int]:
    props: dict = {}
    while True:
        pos = _skip_ws(source, pos)
        if pos >= len(source):
            raise JsxParseError("Unexpected EOF in props", pos, source)
        c = source[pos]
        if c in (">", "/"):
            return props, pos
        m = ATTR_NAME_RE.match(source, pos)
        if not m:
            raise JsxParseError(
                f"Expected attribute name, got {c!r}", pos, source,
            )
        attr_name = m.group(0)
        pos = m.end()

        pos = _skip_ws(source, pos)
        if pos < len(source) and source[pos] == "=":
            pos += 1
            pos = _skip_ws(source, pos)
            value, pos = _parse_attr_value(source, pos)
            props[attr_name] = value
        else:
            props[attr_name] = True


def _parse_attr_value(source: str, pos: int) -> tuple[object, int]:
    if pos >= len(source):
        raise JsxParseError("Unexpected EOF in attribute value", pos, source)
    c = source[pos]
    if c == '"' or c == "'":
        return _parse_string_attr(source, pos, c)
    if c == "{":
        return _parse_expr_attr(source, pos)
    raise JsxParseError(
        f"Expected '\"', \"'\", or '{{' for attribute value, got {c!r}",
        pos, source,
    )


def _parse_string_attr(source: str, pos: int, quote: str) -> tuple[str, int]:
    start = pos + 1
    end = source.find(quote, start)
    if end == -1:
        raise JsxParseError(
            f"Unterminated string attribute (missing {quote})", pos, source,
        )
    return source[start:end], end + 1


def _parse_expr_attr(source: str, pos: int) -> tuple[object, int]:
    assert source[pos] == "{"
    depth = 0
    in_string: Optional[str] = None
    i = pos
    while i < len(source):
        c = source[i]
        if in_string is not None:
            if c == "\\":
                i += 2
                continue
            if c == in_string:
                in_string = None
            i += 1
            continue
        if c in ('"', "'"):
            in_string = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                expr = source[pos + 1:i]
                try:
                    value = py_ast.literal_eval(expr.strip())
                except (ValueError, SyntaxError) as e:
                    raise JsxParseError(
                        f"Cannot parse expression {{{expr}}}: {e}", pos, source,
                    )
                return value, i + 1
        i += 1
    raise JsxParseError("Unterminated expression attribute (missing '}')", pos, source)


def _skip_ws(source: str, pos: int) -> int:
    while pos < len(source) and source[pos] in " \t\r\n":
        pos += 1
    return pos


def _find_matching_close(source: str, pos: int, name: str) -> int:
    depth = 1
    open_re = re.compile(rf"<{name}\b")
    close_re = re.compile(rf"</{name}\s*>")
    i = pos
    while i < len(source):
        if source[i] == "`":
            i = _skip_code_fence_or_inline(source, i)
            continue
        if source[i] == "<":
            close_m = close_re.match(source, i)
            if close_m:
                depth -= 1
                if depth == 0:
                    return i
                i = close_m.end()
                continue
            open_m = open_re.match(source, i)
            if open_m:
                next_char_idx = open_m.end()
                if next_char_idx < len(source) and source[next_char_idx] in " \t\r\n>/":
                    depth += 1
                    i = open_m.end()
                    continue
        i += 1
    raise JsxParseError(f"Unclosed <{name}> tag", pos, source)


def _skip_code_fence_or_inline(source: str, pos: int) -> int:
    if source[pos:pos + 3] == "```":
        end = source.find("```", pos + 3)
        if end == -1:
            return len(source)
        return end + 3
    end = source.find("`", pos + 1)
    if end == -1:
        return pos + 1
    return end + 1


def find_next_component(source: str, start: int = 0) -> Optional[tuple[int, str]]:
    i = start
    while i < len(source):
        if source[i] == "`":
            i = _skip_code_fence_or_inline(source, i)
            continue
        if source[i] == "<" and i + 1 < len(source):
            m = COMPONENT_NAME_RE.match(source, i + 1)
            if m:
                return i, m.group(0)
        i += 1
    return None
