from __future__ import annotations

from . import register, require_prop
from ..citations import render_inline_cite


NAME = "Cite"


def render(ctx, props: dict, children_html: str) -> str:
    key = require_prop("key", props, NAME)
    page = props.get("page")
    return render_inline_cite(ctx.citations, str(key), str(page) if page else None)


register(NAME, render)
