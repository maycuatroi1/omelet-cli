from __future__ import annotations

from . import html_escape, register, require_prop, wrap_card


NAME = "Evidence"
CONFIDENCE_LEVELS = {"low", "medium", "high"}


def render(ctx, props: dict, children_html: str) -> str:
    claim = require_prop("claim", props, NAME)
    confidence = props.get("confidence", "medium")
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "medium"
    body = children_html.strip() if children_html else ""
    return wrap_card(
        ctx,
        f'<aside class="omelet-evidence omelet-evidence--{html_escape(confidence)}" role="note">'
        f'<p class="omelet-evidence__claim">{html_escape(claim)}</p>'
        f'<div class="omelet-evidence__sources">{body}</div>'
        f"</aside>",
    )


register(NAME, render)
