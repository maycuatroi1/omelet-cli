from __future__ import annotations

import sys
from pathlib import Path

import click

from . import components as components_mod
from .citations import CitationError
from .compiler import compile_mdx_path
from .components import ComponentError
from .jsx_tokenizer import JsxParseError
from .migrate import import_footnotes, parse_keymap, rewrite_footnotes
from .sanitize import sanitize


@click.group()
def main() -> None:
    """omelet-mdx: MDX-like authoring for omelet.tech blog."""


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path),
              default=None, help="Output HTML file (default: stdout).")
@click.option("--no-sanitize", is_flag=True, help="Skip Ghost sanitization pass.")
@click.option("--body-only", is_flag=True, help="Skip bibliography section.")
def compile(file: Path, output: Path | None, no_sanitize: bool, body_only: bool) -> None:
    """Compile a .mdx file to HTML."""
    try:
        result = compile_mdx_path(file)
    except (ComponentError, CitationError, JsxParseError) as e:
        click.echo(f"compile error: {e}", err=True)
        sys.exit(1)

    html = result.body_html if body_only else result.html
    if not no_sanitize:
        html = sanitize(html)

    if output:
        output.write_text(html, encoding="utf-8")
        click.echo(f"Wrote {len(html)} chars to {output}", err=True)
    else:
        click.echo(html)


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def check(file: Path) -> None:
    """Validate a .mdx file (parse + render but discard output)."""
    try:
        result = compile_mdx_path(file)
    except (ComponentError, CitationError, JsxParseError) as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)
    click.echo(
        f"OK: {file.name} | {len(result.body_html)} chars body | "
        f"{len(result.used_citations)} citations used"
    )


@main.group()
def components() -> None:
    """Component registry inspection."""


@components.command("list")
def components_list() -> None:
    """List all registered components."""
    for name in components_mod.names():
        click.echo(name)


@main.command("import-footnotes")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--citations-out", type=click.Path(dir_okay=False, path_type=Path),
              default=None)
@click.option("--keymap-out", type=click.Path(dir_okay=False, path_type=Path),
              default=None)
def import_footnotes_cmd(file: Path, citations_out: Path | None,
                         keymap_out: Path | None) -> None:
    """Extract [^N^] footnotes from a .md file into citations.yaml + key_map.txt."""
    cf, km = import_footnotes(file, citations_out, keymap_out)
    click.echo(f"Wrote {cf}")
    click.echo(f"Wrote {km}")
    click.echo("Edit key_map.txt to give entries semantic names, then run rewrite-footnotes.")


@main.command("rewrite-footnotes")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--keymap", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              required=True)
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path),
              default=None, help="Output .mdx file (default: stdout).")
def rewrite_footnotes_cmd(file: Path, keymap: Path, output: Path | None) -> None:
    """Rewrite [^N^] -> [@key] using a keymap, strip appendix + footnote defs."""
    mapping = parse_keymap(keymap)
    text = file.read_text(encoding="utf-8")
    rewritten = rewrite_footnotes(text, mapping)
    if output:
        output.write_text(rewritten, encoding="utf-8")
        click.echo(f"Wrote {output}", err=True)
    else:
        click.echo(rewritten)


if __name__ == "__main__":
    main()
