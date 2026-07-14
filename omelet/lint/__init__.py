"""Content linter for omelet.tech posts.

Mechanizes the rules that until now only existed as prose in CLAUDE.md and
PERSONAL_VOICE.md. A rule that lives only in a document is a rule that a future
agent will violate silently.

    from pathlib import Path
    from omelet.lint import lint_path

    findings = lint_path(Path("blogs/x/main.mdx"))
"""

from __future__ import annotations

from pathlib import Path

from .doc import Doc
from .report import depth_stats, print_report
from .rules import Finding, Options, run

__all__ = ["Doc", "Finding", "Options", "lint_path", "depth_stats", "print_report", "run"]


def lint_path(path: Path, opt: Options | None = None) -> tuple[Doc, list[Finding]]:
    doc = Doc.load(Path(path))
    opt = opt or Options()
    return doc, run(doc, opt)
