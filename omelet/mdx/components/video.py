from __future__ import annotations

import re

from . import ComponentError, opt_prop, register, require_prop, wrap_card


NAME = "Video"
SOLE_PARAGRAPH = re.compile(r"\A<p>(.*)</p>\Z", re.DOTALL)
ALLOWED_SUFFIX = (".mp4", ".webm")
POSTER_SUFFIX = (".png", ".jpg", ".jpeg", ".webp")
MIME = {".mp4": "video/mp4", ".webm": "video/webm"}


def _inline_md(ctx, text: str) -> str:
    text = str(text).strip()
    if not text:
        return ""
    rendered = ctx.render_md(text)
    m = SOLE_PARAGRAPH.match(rendered)
    if m and "<p>" not in m.group(1):
        return m.group(1)
    return rendered


def _suffix(url: str) -> str:
    name = re.sub(r"[?#].*\Z", "", url).rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return "." + name.lower().rsplit(".", 1)[-1]


def _check_url(url: str, prop: str, allowed: tuple) -> str:
    if not url.startswith("https://"):
        raise ComponentError(
            f'<{NAME} {prop}="{url}"> phải là một URL https. omelet publish chỉ '
            f"upload ảnh, không upload video, nên file phải nằm sẵn trên GCS "
            f"trước khi dựng bài."
        )
    if _suffix(url) not in allowed:
        raise ComponentError(
            f'<{NAME} {prop}="{url}"> must point at {" or ".join(allowed)}'
        )
    return url


def render(ctx, props: dict, children_html_unused: str) -> str:
    if len(ctx.parent_chain) > 1:
        parent = ctx.parent_chain[-2]
        raise ComponentError(
            f"<{NAME}> phải dùng ở cấp cao nhất của bài, không được lồng trong "
            f"<{parent}>. Lồng vào thì khối này mất marker riêng và Ghost sẽ "
            f"vứt cả thẻ video."
        )
    src = _check_url(
        str(require_prop("src", props, NAME)).strip(), "src", ALLOWED_SUFFIX
    )
    poster = str(opt_prop("poster", props, "")).strip()
    if poster:
        _check_url(poster, "poster", POSTER_SUFFIX)

    caption = _inline_md(ctx, opt_prop("caption", props, ""))
    extra = str(opt_prop("class", props, "")).strip()
    classes = f"omelet-video {extra}".strip()
    poster_attr = f' poster="{poster}"' if poster else ""
    caption_html = (
        f'<figcaption class="omelet-video__caption">{caption}</figcaption>\n'
        if caption
        else ""
    )
    return wrap_card(
        ctx,
        f'<figure class="{classes}">\n'
        f'<video class="omelet-video__player" controls playsinline muted loop '
        f'preload="metadata"{poster_attr} '
        f'style="display:block;width:100%;height:auto;">\n'
        f'<source src="{src}" type="{MIME[_suffix(src)]}">\n'
        f"Trình duyệt này không phát được video.\n"
        f"</video>\n"
        f"{caption_html}"
        f"</figure>",
    )


render.raw_children = True
register(NAME, render)
