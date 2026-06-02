from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml


FOOTNOTE_DEF_RE = re.compile(r"^\s*\[\^(\d+)\^?\]:\s*(.+)$")
FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\^?\]")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
APPENDIX_HEADING_RE = re.compile(
    r"^##\s+(?:Phụ lục|Appendix|Bibliography|Citations|References)[:\s]*.*$",
    re.MULTILINE | re.IGNORECASE,
)


def extract_footnotes(md_text: str) -> dict[str, dict]:
    notes: dict[str, dict] = {}
    for line in md_text.splitlines():
        m = FOOTNOTE_DEF_RE.match(line)
        if not m:
            continue
        num = m.group(1)
        body = m.group(2).strip()
        url_match = URL_RE.search(body)
        url = url_match.group(0) if url_match else ""
        notes[num] = {"body": body, "url": url}
    return notes


def auto_key(num: str, body: str, url: str, used_keys: set[str]) -> str:
    base = ""
    if url:
        host = urlparse(url).netloc.replace("www.", "")
        base = host.split(".")[0] if host else ""
    if not base:
        base = re.sub(r"\W+", "-", body[:30].lower()).strip("-") or f"ref-{num}"
    year_match = re.search(r"\b(20\d{2})\b", body)
    year = year_match.group(1) if year_match else ""
    candidate = f"{base}-{year}" if year else base
    if candidate not in used_keys:
        return candidate
    i = 2
    while f"{candidate}-{i}" in used_keys:
        i += 1
    return f"{candidate}-{i}"


def import_footnotes(md_path: Path, citations_path: Optional[Path] = None,
                     keymap_path: Optional[Path] = None) -> tuple[Path, Path]:
    md_text = md_path.read_text(encoding="utf-8")
    notes = extract_footnotes(md_text)
    if not notes:
        raise ValueError(f"No footnotes found in {md_path}")

    used: set[str] = set()
    keymap: dict[str, str] = {}
    citations: dict[str, dict] = {}
    for num, data in notes.items():
        key = auto_key(num, data["body"], data["url"], used)
        used.add(key)
        keymap[num] = key
        entry: dict = {
            "type": "news",
            "title": _extract_title(data["body"], data["url"]),
        }
        if data["url"]:
            entry["url"] = data["url"]
        entry["note"] = data["body"]
        citations[key] = entry

    out_citations = citations_path or md_path.parent / "citations.yaml"
    out_keymap = keymap_path or md_path.parent / "key_map.txt"
    out_citations.write_text(
        yaml.safe_dump(citations, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    out_keymap.write_text(
        "\n".join(f"[^{num}^] -> {key}" for num, key in keymap.items()) + "\n",
        encoding="utf-8",
    )
    return out_citations, out_keymap


def _extract_title(body: str, url: str) -> str:
    cleaned = body
    if url:
        cleaned = cleaned.replace(url, "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -—:,.")
    return cleaned[:120] if cleaned else (url[:120] if url else "untitled")


def parse_keymap(keymap_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in keymap_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"\[\^(\d+)\^?\]\s*->\s*(\S+)", line)
        if m:
            mapping[m.group(1)] = m.group(2)
    return mapping


def rewrite_footnotes(md_text: str, keymap: dict[str, str]) -> str:
    def repl(m):
        num = m.group(1)
        key = keymap.get(num)
        if not key:
            return m.group(0)
        return f"[@{key}]"

    body = FOOTNOTE_REF_RE.sub(repl, md_text)

    body = _strip_appendix_section(body)

    body = re.sub(r"^\s*\[\^\d+\^?\]:.*$\n?", "", body, flags=re.MULTILINE)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def _strip_appendix_section(text: str) -> str:
    m = APPENDIX_HEADING_RE.search(text)
    if not m:
        return text
    end = len(text)
    next_heading = re.search(r"^##\s+", text[m.end():], re.MULTILINE)
    if next_heading:
        end = m.end() + next_heading.start()
    return text[:m.start()].rstrip() + "\n\n" + text[end:].lstrip()
