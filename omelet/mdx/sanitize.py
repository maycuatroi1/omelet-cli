from __future__ import annotations

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


def sanitize(html: str) -> str:
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
