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
# image and concatenates every caption. Wrapping a block in these markers is
# the documented way to hand Ghost that block verbatim instead.
#
# What sits between the markers therefore skips bleach too. The allowlist
# above has no SVG vocabulary and drops `style`, so a hand-drawn diagram came
# out as its bare text nodes with every shape gone: a silent corruption that
# only surfaces on the published post. A block the author explicitly marked
# as verbatim is hand-written in a tracked repo, not user input, so the
# allowlist was never the security boundary here. _check_raw keeps the part
# that still is - a pasted third-party embed carrying script or an inline
# event handler fails the build instead of shipping.
#
# That is the whole threat model, and it is narrower than "no script in a post".
# An interactive demo the author wrote themselves is not a pasted embed, so the
# <Widget> component opens its card with WIDGET_SENTINEL and sanitize hands that
# one block back untouched. The sentinel is not a password, it is a provenance
# tag: only the compiler emits it, immediately after BEGIN_MARKER, around a
# .html file read from the post's own directory. Markup a writer pasted from
# elsewhere arrives without it and still fails the build.
KG_HTML_CARD_MARKER = re.compile(r"(<!--kg-card-(?:begin|end): html-->)")
BEGIN_MARKER = "<!--kg-card-begin: html-->"
END_MARKER = "<!--kg-card-end: html-->"
WIDGET_SENTINEL = "<!--omelet:widget-->"

TAG = re.compile(r"<[/a-zA-Z][^>]*>")
SCRIPT_TAG = re.compile(r"<\s*/?\s*script\b", re.IGNORECASE)
EVENT_ATTR = re.compile(r"\son[a-zA-Z]+\s*=", re.IGNORECASE)
JS_URL = re.compile(r"=\s*[\"']?\s*javascript\s*:", re.IGNORECASE)

# Outside the markers bleach would delete these without a word. They are only
# ever written on purpose, so say so instead of publishing a hole in the post.
RAW_ONLY_TAG = re.compile(r"<\s*(svg|math)\b", re.IGNORECASE)


class SanitizeError(Exception):
    pass


def sanitize(html: str) -> str:
    out: list[str] = []
    verbatim = False
    for part in KG_HTML_CARD_MARKER.split(html):
        if KG_HTML_CARD_MARKER.fullmatch(part):
            opening = part == BEGIN_MARKER
            if opening and verbatim:
                raise SanitizeError(
                    f"{BEGIN_MARKER} opened twice without a closing {END_MARKER}"
                )
            if not opening and not verbatim:
                raise SanitizeError(f"{END_MARKER} has no matching {BEGIN_MARKER}")
            verbatim = opening
            out.append(part)
        elif verbatim:
            if part.lstrip().startswith(WIDGET_SENTINEL):
                out.append(part)
            else:
                out.append(_check_raw(part))
        else:
            out.append(_clean(_check_needs_marker(part)))
    if verbatim:
        raise SanitizeError(f"{BEGIN_MARKER} is never closed by {END_MARKER}")
    return "".join(out)


def _check_raw(fragment: str) -> str:
    for tag in TAG.findall(fragment):
        if SCRIPT_TAG.match(tag) or EVENT_ATTR.search(tag) or JS_URL.search(tag):
            raise SanitizeError(
                f"HTML card holds executable markup, remove it: {tag[:120]}"
            )
    return fragment


def _check_needs_marker(fragment: str) -> str:
    m = RAW_ONLY_TAG.search(fragment)
    if m:
        raise SanitizeError(
            f"<{m.group(1)}> outside an HTML card would be stripped before Ghost "
            f"sees it. Wrap the block in <Diagram> or in {BEGIN_MARKER} ... "
            f"{END_MARKER}."
        )
    return fragment


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
