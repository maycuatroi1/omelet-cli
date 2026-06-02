from __future__ import annotations

from . import html_escape, register, require_prop


NAME = "Source"
ALLOWED_TYPES = {"news", "paper", "sec-filing", "press-release", "primary-quote", "podcast", "report", "other"}


def render(ctx, props: dict, children_html: str) -> str:
    url = require_prop("url", props, NAME)
    date = props.get("date", "")
    src_type = props.get("type", "news")
    if src_type not in ALLOWED_TYPES:
        src_type = "other"
    body = ctx.render_md(children_html) if children_html else ""
    body_clean = body.strip()
    if body_clean.startswith("<p>") and body_clean.endswith("</p>") and body_clean.count("<p>") == 1:
        body_clean = body_clean[3:-4]
    date_html = (
        f'<time class="omelet-source__date" datetime="{html_escape(date)}">{html_escape(date)}</time>'
        if date else ""
    )
    return (
        f'<div class="omelet-source omelet-source--{html_escape(src_type)}">'
        f'<a href="{html_escape(url)}" rel="noopener" target="_blank" class="omelet-source__link">'
        f'{html_escape(url)}</a>'
        f'{(" " + date_html) if date_html else ""}'
        f'{(" — " + body_clean) if body_clean else ""}'
        f"</div>"
    )


register(NAME, render)
