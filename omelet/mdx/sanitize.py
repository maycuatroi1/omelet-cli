from __future__ import annotations

import re

import bleach


GHOST_ALLOWED_TAGS: set[str] = {
    "a", "abbr", "address", "article", "aside", "b", "blockquote", "br",
    "caption", "cite", "code", "col", "colgroup", "dd", "del", "details",
    "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "i", "img", "ins",
    "kbd", "li", "main", "mark", "nav", "ol", "p", "picture", "pre", "q",
    "s", "samp", "section", "small", "source", "span", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time",
    "tr", "u", "ul", "var", "wbr",
}

GHOST_ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "title", "role", "lang", "dir", "aria-label", "aria-hidden"],
    "a": ["href", "name", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "source": ["src", "srcset", "type", "media", "sizes"],
    "time": ["datetime"],
    "th": ["scope", "colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
    "ol": ["start", "type"],
    "li": ["value"],
    "details": ["open"],
    "blockquote": ["cite"],
    "q": ["cite"],
    "del": ["cite", "datetime"],
    "ins": ["cite", "datetime"],
}


# Ghost's HTML-to-lexical converter maps any <figure> it sees onto its own
# image card, which collapses a multi-image figure grid down to the first
# image and concatenates every caption. These markers are the documented way
# to hand Ghost a block verbatim instead. They are HTML comments, so
# strip_comments=True below would delete them before Ghost ever sees them.
# The markers always sit between complete blocks, so splitting on them leaves
# balanced fragments that clean independently and rejoin losslessly. A
# placeholder swap would be shorter but bleach drops the sentinel characters
# that would make one collision-proof.
KG_HTML_CARD_MARKER = re.compile(r"(<!--kg-card-(?:begin|end): html-->)")


def sanitize(html: str) -> str:
    parts = KG_HTML_CARD_MARKER.split(html)
    return "".join(
        part if KG_HTML_CARD_MARKER.fullmatch(part) else _clean(part)
        for part in parts
    )


def _clean(html: str) -> str:
    return bleach.clean(
        html,
        tags=GHOST_ALLOWED_TAGS,
        attributes=GHOST_ALLOWED_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
        strip_comments=True,
    )


def is_invariant(html: str) -> bool:
    return sanitize(html) == html
