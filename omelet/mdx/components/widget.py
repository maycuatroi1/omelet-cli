from __future__ import annotations

import re

from . import ComponentError, opt_prop, register, require_prop, wrap_card


NAME = "Widget"
SOLE_PARAGRAPH = re.compile(r"\A<p>(.*)</p>\Z", re.DOTALL)
ALLOWED_SUFFIX = (".html",)
WIDGET_SENTINEL = "<!--omelet:widget-->"


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
    src = str(require_prop("src", props, NAME)).strip()
    if not src:
        raise ComponentError(f'<{NAME}> needs a src file, but src="" is empty')
    raw = _read_src(ctx, src)
    if not raw:
        raise ComponentError(f'<{NAME} src="{src}"> holds an empty file')

    caption = _inline_md(ctx, opt_prop("caption", props, ""))
    extra = str(opt_prop("class", props, "")).strip()
    classes = f"omelet-widget {extra}".strip()
    caption_html = (
        f'<figcaption class="omelet-widget__caption">{caption}</figcaption>\n'
        if caption
        else ""
    )
    return wrap_card(
        ctx,
        f"{WIDGET_SENTINEL}\n"
        f'<figure class="{classes}">\n'
        f"{raw}\n"
        f"{caption_html}"
        f"</figure>",
    )


render.raw_children = True
register(NAME, render)
