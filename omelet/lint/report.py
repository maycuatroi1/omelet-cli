"""Terminal output for `omelet lint`.

Two halves. The findings tell you what to fix. The depth panel tells you what the
post *is* - how many words, how many sources, how many of those sources are
primary, whether you made anything yourself. The panel has no pass/fail: it is
there so you can look at a post and see, in five numbers, whether the work was
actually done.
"""

from __future__ import annotations

import click

from .doc import Doc
from .rules import Finding, Options, _is_primary

_COLOR = {"error": "red", "warn": "yellow", "info": "cyan"}


def depth_stats(doc: Doc, opt: Options) -> dict:
    used = [k for k in doc.used_keys if k in doc.citations]
    primary = [k for k in used if _is_primary(doc.citations[k])]
    sentences = [s for b in doc.prose_blocks for s in doc.sentences(b)]
    avg_len = (
        sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0.0
    )
    bullet_words = sum(b.words for b in doc.blocks if b.kind == "list")
    total_words = doc.word_count + bullet_words
    return {
        "words": doc.word_count,
        "sentences": len(sentences),
        "avg_sentence": round(avg_len, 1),
        "citations_used": len(doc.used_keys),
        "citations_resolved": len(used),
        "primary": len(primary),
        "primary_ratio": round(len(primary) / len(used), 2) if used else 0.0,
        "own_artifacts": len(doc.local_images),
        "bullet_pct": int(100 * bullet_words / total_words) if total_words else 0,
    }


def print_report(doc: Doc, findings: list[Finding], opt: Options, show_stats: bool = True) -> None:
    rel = doc.path
    for f in findings:
        loc = click.style(f"{rel}:{f.line}:{f.col}", bold=True)
        rid = click.style(f"{f.rule:<9}", fg=_COLOR.get(f.severity, "white"))
        click.echo(f"{loc}  {rid} {f.message}")
        click.echo(f"{' ' * 4}-> {f.fix}")

    if show_stats:
        s = depth_stats(doc, opt)
        click.echo()
        click.echo(click.style(" do sau ".center(56, "-"), bold=True))
        click.echo(f"  chữ                {s['words']}")
        click.echo(f"  câu / dài trung bình  {s['sentences']} câu, {s['avg_sentence']} chữ/câu")
        click.echo(
            f"  citation           {s['citations_resolved']}/{s['citations_used']} resolve được, "
            f"{s['primary']} primary ({int(s['primary_ratio'] * 100)}%)"
        )
        click.echo(f"  artifact tự làm    {s['own_artifacts']} hình/biểu đồ local")
        click.echo(f"  bullet             {s['bullet_pct']}% số chữ")

    errors = sum(1 for f in findings if f.severity == "error")
    warns = sum(1 for f in findings if f.severity == "warn")
    click.echo()
    if not findings:
        click.echo(click.style("  không có phát hiện nào.", fg="green"))
    else:
        click.echo(
            "  "
            + click.style(f"{errors} error", fg="red" if errors else "green")
            + ", "
            + click.style(f"{warns} warn", fg="yellow" if warns else "green")
        )
