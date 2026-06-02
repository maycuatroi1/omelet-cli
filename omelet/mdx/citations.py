from __future__ import annotations

import difflib
import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class CitationError(Exception):
    pass


@dataclass
class CiteEntry:
    key: str
    title: str = ""
    author: str = ""
    publisher: str = ""
    date: str = ""
    url: str = ""
    note: str = ""
    type: str = "news"
    raw: dict = field(default_factory=dict)


@dataclass
class CiteRegistry:
    entries: dict[str, CiteEntry] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    _numbers: dict[str, int] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        return key in self.entries

    def closest(self, key: str, n: int = 3) -> list[str]:
        return difflib.get_close_matches(key, self.entries.keys(), n=n)

    def use(self, key: str) -> int:
        if key not in self._numbers:
            self._order.append(key)
            self._numbers[key] = len(self._order)
        return self._numbers[key]

    def used_keys(self) -> list[str]:
        return list(self._order)


def load_citations(path: Path) -> CiteRegistry:
    if not path.exists():
        return CiteRegistry()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise CitationError(f"{path}: top-level YAML must be a mapping of key -> entry")
    reg = CiteRegistry()
    for key, value in raw.items():
        if not isinstance(value, dict):
            raise CitationError(f"{path}: entry {key!r} must be a mapping")
        entry = CiteEntry(
            key=key,
            title=str(value.get("title", "")),
            author=_join_authors(value.get("author") or value.get("authors")),
            publisher=str(value.get("publisher", "")),
            date=str(value.get("date", "")),
            url=str(value.get("url", "")),
            note=str(value.get("note", "")),
            type=str(value.get("type", "news")),
            raw=value,
        )
        reg.entries[key] = entry
    return reg


def _join_authors(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def render_inline_cite(reg: CiteRegistry, key: str, page: Optional[str] = None) -> str:
    if not reg.has(key):
        suggestions = reg.closest(key)
        hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        raise CitationError(f"Unknown citation key {key!r}.{hint}")
    number = reg.use(key)
    page_suffix = f", p.{html.escape(page)}" if page else ""
    return (
        f'<sup class="omelet-cite">'
        f'<a href="#cite-{html.escape(key)}" id="citeref-{html.escape(key)}">'
        f'[{number}]{page_suffix}</a></sup>'
    )


def render_bibliography(reg: CiteRegistry, heading: str = "Phụ lục: Citations") -> str:
    if not reg.used_keys():
        return ""
    count = len(reg.used_keys())
    parts = [
        '<details class="omelet-bibliography">',
        (
            '<summary class="omelet-bibliography__summary">'
            f"{html.escape(heading)} "
            f'<span class="omelet-bibliography__count">({count})</span>'
            "</summary>"
        ),
        '<ol class="omelet-bibliography__list">',
    ]
    for key in reg.used_keys():
        entry = reg.entries[key]
        parts.append(_render_entry(entry))
    parts.append("</ol>")
    parts.append("</details>")
    return "\n".join(parts)


def _render_entry(entry: CiteEntry) -> str:
    bits: list[str] = []
    if entry.author:
        bits.append(html.escape(entry.author))
    if entry.title:
        title_html = f'<em>{html.escape(entry.title)}</em>'
        if entry.url:
            title_html = f'<a href="{html.escape(entry.url)}">{title_html}</a>'
        bits.append(title_html)
    if entry.publisher:
        bits.append(html.escape(entry.publisher))
    if entry.date:
        bits.append(html.escape(entry.date))
    body = ". ".join(b for b in bits if b)
    note = ""
    if entry.note:
        note = f' <span class="omelet-bibliography__note">{html.escape(entry.note)}</span>'
    return (
        f'<li id="cite-{html.escape(entry.key)}" '
        f'class="omelet-bibliography__entry omelet-bibliography__entry--{html.escape(entry.type)}">'
        f"{body}.{note}"
        f"</li>"
    )
