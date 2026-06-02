from __future__ import annotations

import re

from . import ComponentError, html_escape, register, require_prop
from ..jsx_tokenizer import parse_component_at


NAME = "Analogy"
SLOTS = ("Everyday", "Technical", "Implication")
SLOT_LABELS = {
    "Everyday": "Đời thường",
    "Technical": "Kỹ thuật",
    "Implication": "Hệ quả",
}


def _extract_slots(children_raw: str) -> dict[str, str]:
    slots: dict[str, str] = {}
    pos = 0
    n = len(children_raw)
    while pos < n:
        while pos < n and children_raw[pos] in " \t\r\n":
            pos += 1
        if pos >= n:
            break
        if children_raw[pos] != "<":
            raise ComponentError(
                f"<Analogy> children must be exactly <Everyday>, <Technical>, "
                f"<Implication> blocks; found stray text at offset {pos}"
            )
        node = parse_component_at(children_raw, pos)
        if node is None:
            raise ComponentError(f"<Analogy> child at offset {pos} could not parse")
        if node.name not in SLOTS:
            raise ComponentError(
                f"<Analogy> only allows {SLOTS}, got <{node.name}>"
            )
        if node.name in slots:
            raise ComponentError(f"<Analogy> has duplicate <{node.name}> slot")
        slots[node.name] = node.children_raw
        pos = node.end
    return slots


def render(ctx, props: dict, children_html_unused: str) -> str:
    title = require_prop("title", props, NAME)
    children_raw = props.pop("__children_raw__", "")
    slots = _extract_slots(children_raw)
    if "Everyday" not in slots or "Technical" not in slots:
        missing = [s for s in ("Everyday", "Technical") if s not in slots]
        raise ComponentError(
            f"<Analogy> missing required slot(s): {missing}"
        )
    panels: list[str] = []
    for slot in SLOTS:
        if slot not in slots:
            continue
        body = ctx.render_md(slots[slot]) if slots[slot].strip() else ""
        label = SLOT_LABELS[slot]
        panels.append(
            f'<div class="omelet-analogy__panel omelet-analogy__panel--{slot.lower()}">'
            f'<h4 class="omelet-analogy__label">{html_escape(label)}</h4>'
            f"<div class=\"omelet-analogy__content\">{body}</div>"
            f"</div>"
        )
    return (
        f'<figure class="omelet-analogy">'
        f'<figcaption class="omelet-analogy__title">{html_escape(title)}</figcaption>'
        f"{''.join(panels)}"
        f"</figure>"
    )


register(NAME, render)
