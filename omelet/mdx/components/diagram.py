from __future__ import annotations

import re
import textwrap

from . import BEGIN_MARKER, END_MARKER, ComponentError, opt_prop, register, wrap_card


NAME = "Diagram"
SOLE_PARAGRAPH = re.compile(r"\A<p>(.*)</p>\Z", re.DOTALL)
ALLOWED_SUFFIX = (".svg", ".html")


def _inline_md(ctx, text: str) -> str:
    text = str(text).strip()
    if not text:
        return ""
    rendered = ctx.render_md(text)
    m = SOLE_PARAGRAPH.match(rendered)
    if m and "<p>" not in m.group(1):
        return m.group(1)
    return rendered


def _read_src(ctx, src: str) -> str:
    if ctx.assets_dir is None:
        raise ComponentError(
            f'<{NAME} src="{src}"> needs a file on disk, but this compile has no '
            f"assets directory"
        )
    path = (ctx.assets_dir / src).resolve()
    if path.suffix.lower() not in ALLOWED_SUFFIX:
        raise ComponentError(
            f'<{NAME} src="{src}"> must point at {" or ".join(ALLOWED_SUFFIX)}'
        )
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ComponentError(f'<{NAME} src="{src}"> not found at {path}')
    body = re.sub(r"<\?xml[^>]*\?>\s*", "", text)
    body = re.sub(r"<!DOCTYPE[^>]*>\s*", "", body, flags=re.IGNORECASE)
    return body.strip()


def render(ctx, props: dict, children_html_unused: str) -> str:
    raw = textwrap.dedent(str(props.pop("__children_raw__", ""))).strip()
    src = str(opt_prop("src", props, "")).strip()

    if src and raw:
        raise ComponentError(
            f"<{NAME}> takes either a src file or inline children, not both"
        )
    if src:
        raw = _read_src(ctx, src)
    if not raw:
        raise ComponentError(
            f"<{NAME}> is empty; give it a src file or raw SVG/HTML children"
        )
    if raw.startswith("!["):
        raise ComponentError(
            f"<{NAME}> children are raw markup, not markdown. An image file "
            f"belongs in a plain ![alt](path) line."
        )

    caption = _inline_md(ctx, opt_prop("caption", props, ""))
    extra = str(opt_prop("class", props, "")).strip()
    classes = f"omelet-diagram {extra}".strip()
    caption_html = (
        f'<figcaption class="omelet-diagram__caption">{caption}</figcaption>\n'
        if caption
        else ""
    )
    return wrap_card(
        ctx,
        f'<figure class="{classes}">\n'
        f"{raw}\n"
        f"{caption_html}"
        f"</figure>",
    )


render.raw_children = True
register(NAME, render)
