from __future__ import annotations

import re

from . import ComponentError, html_escape, register, require_prop


NAME = "Scenario"
PROBABILITY_RE = re.compile(r"^\d{1,3}(-\d{1,3})?$")


def render(ctx, props: dict, children_html: str) -> str:
    title = require_prop("title", props, NAME)
    probability = str(require_prop("probability", props, NAME))
    if not PROBABILITY_RE.match(probability):
        raise ComponentError(
            f"<Scenario probability={probability!r}> must match e.g. '35' or '35-45'"
        )
    trigger = require_prop("trigger", props, NAME)
    timeline = props.get("timeline", "")
    body = ctx.render_md(children_html) if children_html else ""
    prob_display = probability.replace("-", "–") + "%"
    timeline_html = (
        f'<dt class="omelet-scenario__label">Khi nào</dt>'
        f'<dd class="omelet-scenario__timeline">{html_escape(timeline)}</dd>'
        if timeline else ""
    )
    return (
        f'<section class="omelet-scenario">'
        f'<header class="omelet-scenario__header">'
        f'<h3 class="omelet-scenario__title">{html_escape(title)}</h3>'
        f'<span class="omelet-scenario__probability">{html_escape(prob_display)}</span>'
        f'<dl class="omelet-scenario__meta">'
        f'<dt class="omelet-scenario__label">Trigger</dt>'
        f'<dd class="omelet-scenario__trigger">{html_escape(trigger)}</dd>'
        f"{timeline_html}"
        f"</dl>"
        f"</header>"
        f'<div class="omelet-scenario__body">{body}</div>'
        f"</section>"
    )


register(NAME, render)
