"""Document model for the content linter.

The whole point of this module is to give the rules a view of the post where
code, math and URLs have already been blanked out, so a rule that hunts for the
em-dash does not fire on a code sample that legitimately contains one. Masking
replaces the excluded spans with spaces of the same length, which keeps every
character offset intact - a rule can report `line:col` straight from an index
into the masked text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Spans that rules must never see. Order matters: fences before inline code.
_MASK_PATTERNS = [
    re.compile(r"```.*?```", re.DOTALL),          # fenced code
    re.compile(r"~~~.*?~~~", re.DOTALL),          # alt fenced code
    re.compile(r"`[^`\n]+`"),                     # inline code
    re.compile(r"<!--.*?-->", re.DOTALL),         # html comments
    re.compile(r"\$\$.*?\$\$", re.DOTALL),        # display math
    re.compile(r"(?<!\\)\$[^$\n]+\$"),            # inline math
    re.compile(r"https?://\S+"),                  # bare URLs
    re.compile(r"\]\([^)\s]+\)"),                 # markdown link targets
]

_SENTENCE_END = re.compile(r"(?<![0-9])[.!?]+(?:\s+|$)")

CITE_KEY_RE = re.compile(r"\[@([A-Za-z0-9][A-Za-z0-9._-]*)\]")
_EVIDENCE_OF_SOURCE = re.compile(
    r"\[@[A-Za-z0-9]|<Cite\b|<Source\b|<Evidence\b|\[\^|\]\(https?://",
)

_BULLET = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_LOCAL_IMAGE = re.compile(r"!\[[^\]]*\]\((?!https?://)([^)]+)\)")


def _mask(text: str) -> str:
    chars = list(text)
    for pat in _MASK_PATTERNS:
        for m in pat.finditer("".join(chars)):
            for i in range(m.start(), m.end()):
                if chars[i] != "\n":
                    chars[i] = " "
    return "".join(chars)


@dataclass
class Block:
    """One blank-line-separated chunk of the post."""

    kind: str  # prose | heading | list | table | image | jsx | quote | blank
    text: str  # masked text
    start: int  # char offset into masked body

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass
class Doc:
    path: Path
    raw: str
    frontmatter: dict
    body: str  # unmasked, frontmatter stripped
    masked: str  # same length as body, code/math/urls blanked
    body_offset: int  # char offset of body inside raw
    blocks: list[Block] = field(default_factory=list)
    citations: dict = field(default_factory=dict)  # key -> entry dict
    citations_path: Optional[Path] = None

    # -- construction ----------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "Doc":
        raw = path.read_text(encoding="utf-8")
        fm: dict = {}
        body = raw
        offset = 0
        m = FRONTMATTER_RE.match(raw)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                fm = {}
            if not isinstance(fm, dict):
                fm = {}
            body = raw[m.end():]
            offset = m.end()

        doc = cls(
            path=path,
            raw=raw,
            frontmatter=fm,
            body=body,
            masked=_mask(body),
            body_offset=offset,
        )
        doc.blocks = doc._split_blocks()
        doc._load_citations()
        return doc

    def _split_blocks(self) -> list[Block]:
        blocks: list[Block] = []
        pos = 0
        for chunk in re.split(r"\n\s*\n", self.masked):
            start = self.masked.find(chunk, pos) if chunk else pos
            pos = start + len(chunk)
            stripped = chunk.strip()
            if not stripped:
                continue
            first = stripped.splitlines()[0].lstrip()
            if first.startswith("#"):
                kind = "heading"
            elif first.startswith(">"):
                kind = "quote"
            elif first.startswith("!["):
                kind = "image"
            elif first.startswith("|"):
                kind = "table"
            elif first.startswith("<"):
                kind = "jsx"
            elif _BULLET.match(first):
                kind = "list"
            elif not stripped.replace(" ", " ").strip():
                kind = "blank"
            else:
                kind = "prose"
            blocks.append(Block(kind=kind, text=chunk, start=start))
        return blocks

    def _load_citations(self) -> None:
        name = self.frontmatter.get("citations") or "citations.yaml"
        cpath = self.path.parent / str(name)
        if not cpath.exists():
            return
        try:
            data = yaml.safe_load(cpath.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return
        if isinstance(data, dict):
            self.citations = {k: v for k, v in data.items() if isinstance(v, dict)}
            self.citations_path = cpath

    # -- views used by rules ---------------------------------------------

    @property
    def prose_blocks(self) -> list[Block]:
        return [b for b in self.blocks if b.kind in ("prose", "quote")]

    @property
    def prose_text(self) -> str:
        return "\n\n".join(b.text for b in self.prose_blocks)

    @property
    def word_count(self) -> int:
        return len(self.prose_text.split())

    @property
    def used_keys(self) -> list[str]:
        seen: list[str] = []
        for m in CITE_KEY_RE.finditer(self.masked):
            if m.group(1) not in seen:
                seen.append(m.group(1))
        return seen

    @property
    def local_images(self) -> list[str]:
        """Images the author made.

        A post that has already been published has its images rewritten to GCS
        URLs, so counting only relative refs would call a post with seven
        hand-drawn matplotlib charts 'artifact-free'. Count what is on disk next
        to the post too. `featured.*` does not count: a generated cover image is
        decoration, not evidence.
        """
        refs = _LOCAL_IMAGE.findall(self.body)
        on_disk = [
            p.name
            for p in self.path.parent.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp")
            and not p.stem.lower().startswith("featured")
        ] if self.path.parent.is_dir() else []
        return sorted(set(refs) | set(on_disk))

    def line_col(self, idx: int) -> tuple[int, int]:
        """Map a masked-body offset back to a 1-indexed line/col in the file."""
        abs_idx = self.body_offset + idx
        line = self.raw.count("\n", 0, abs_idx) + 1
        last_nl = self.raw.rfind("\n", 0, abs_idx)
        return line, abs_idx - last_nl

    def sentences(self, block: Block) -> list[str]:
        parts = _SENTENCE_END.split(block.text)
        return [p.strip() for p in parts if p.strip()]

    def has_source(self, text: str) -> bool:
        return bool(_EVIDENCE_OF_SOURCE.search(text))

    @property
    def ignored_rules(self) -> set[str]:
        raw = self.frontmatter.get("lint_ignore") or []
        if isinstance(raw, str):
            raw = [raw]
        return {str(r).strip().upper() for r in raw}
