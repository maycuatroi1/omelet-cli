"""Mechanical integrity rules for blog source files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterator

from .doc import Doc

Severity = str  # "error" | "warn" | "info"


@dataclass
class Finding:
    rule: str
    severity: Severity
    line: int
    col: int
    message: str
    fix: str


@dataclass
class Options:
    pass


RULES: list[tuple[str, Severity, Callable]] = []


def rule(rid: str, severity: Severity):
    def deco(fn):
        RULES.append((rid, severity, fn))
        return fn

    return deco


@rule("DEPTH-D3", "error")
def citation_dead(doc: Doc, opt: Options):
    if not doc.citations:
        if doc.used_keys:
            yield 0, (
                f"bài dùng {len(doc.used_keys)} citation key nhưng không có citations.yaml"
            ), "tạo citations.yaml trong folder bài viết"
        return
    from .doc import CITE_KEY_RE

    for m in CITE_KEY_RE.finditer(doc.masked):
        key = m.group(1)
        if key not in doc.citations:
            import difflib

            near = difflib.get_close_matches(key, list(doc.citations), n=1)
            hint = f" (ý bạn là '{near[0]}'?)" if near else ""
            yield m.start(), f"citation key không tồn tại: [@{key}]{hint}", (
                "sửa key hoặc thêm entry vào citations.yaml"
            )


# --------------------------------------------------------------------------
# FORMAT
# --------------------------------------------------------------------------


@rule("FMT-F1", "error")
def frontmatter(doc: Doc, opt: Options):
    fm = doc.frontmatter
    if not fm:
        yield 0, "thiếu frontmatter", "thêm frontmatter với title + description"
        return
    for field_name in ("title", "description"):
        if not str(fm.get(field_name, "")).strip():
            yield 0, f"frontmatter thiếu '{field_name}'", f"thêm {field_name} vào frontmatter"
    desc = str(fm.get("description", ""))
    if len(desc) > 160:
        yield 0, f"description dài {len(desc)} ký tự (tối đa 160)", "cắt ngắn description"


_UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$\s?\d")


@rule("FMT-F2", "error")
def unescaped_dollar(doc: Doc, opt: Options):
    for m in _UNESCAPED_DOLLAR.finditer(doc.masked):
        yield m.start(), f'"{m.group(0)}" - KaTeX sẽ nuốt cặp $...$ thành công thức', (
            r"escape thành \$"
        )


def run(doc: Doc, opt: Options) -> list[Finding]:
    findings: list[Finding] = []
    ignored = doc.ignored_rules
    for rid, severity, fn in RULES:
        if rid in ignored:
            continue
        for idx, message, fix in fn(doc, opt):
            line, col = doc.line_col(idx)
            findings.append(Finding(rid, severity, line, col, message, fix))
    findings.sort(key=lambda f: (f.line, f.col, f.rule))
    return findings
