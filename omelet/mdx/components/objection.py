from __future__ import annotations

from . import ComponentError, html_escape, register, require_prop, wrap_card


NAME = "Objection"
STRENGTH_LEVELS = {"weak", "moderate", "strong"}


def render(ctx, props: dict, children_html: str) -> str:
    claim = require_prop("claim", props, NAME)
    strength = props.get("strength", "moderate")
    if strength not in STRENGTH_LEVELS:
        strength = "moderate"
    body = ctx.render_md(children_html) if children_html else ""
    if not body.strip():
        raise ComponentError(
            f"<Objection> requires a rebuttal body (children cannot be empty)"
        )
    return wrap_card(
        ctx,
        f'<section class="omelet-objection omelet-objection--{html_escape(strength)}">'
        f'<blockquote class="omelet-objection__claim">'
        f'<p>{html_escape(claim)}</p>'
        f"</blockquote>"
        f'<div class="omelet-objection__rebuttal">{body}</div>'
        f"</section>",
    )


register(NAME, render)
