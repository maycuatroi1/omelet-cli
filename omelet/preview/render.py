from __future__ import annotations

import html as _html
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from omelet.mdx.compiler import compile_mdx_string


@dataclass
class RenderOutput:
    html: str
    title: str
    error: Optional[str] = None


SHELL = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — preview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;600&family=Caveat:wght@400;600&display=swap">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.10.0/styles/atom-one-dark.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" onload="renderMathInElement(document.body, {{delimiters: [{{left: '\\\\[', right: '\\\\]', display: true}}, {{left: '\\\\(', right: '\\\\)', display: false}}], throwOnError: false}});"></script>
{theme_link}
<link rel="stylesheet" href="/__assets__/components.css">
<style>
{base_css}
.omelet-math.math-display {{ margin: 1.2rem 0; text-align: center; overflow-x: auto; }}
.omelet-math.math-inline {{ display: inline; }}
</style>
</head>
<body>
<div class="omelet-preview-bar">
  <span class="omelet-preview-bar__dot"></span>
  <span>preview · <code>{slug}</code></span>
  <span class="omelet-preview-bar__spacer"></span>
  <span id="omelet-preview-status">live</span>
</div>
<main class="gh-main">
  <article class="gh-article post">
    <header class="gh-article-header gh-canvas">
      <h1 class="gh-article-title is-title">{title_escaped}</h1>
      {excerpt_block}
    </header>
    <section class="gh-content gh-canvas is-body">
      {body}
    </section>
  </article>
</main>
<script>
(function(){{
  var last = null;
  var status = document.getElementById('omelet-preview-status');
  function poll(){{
    fetch('/__mtime__', {{cache: 'no-store'}}).then(function(r){{
      if(!r.ok) throw new Error('mtime ' + r.status);
      return r.json();
    }}).then(function(j){{
      if(last !== null && j.token !== last){{
        status.textContent = 'reloading';
        location.reload();
        return;
      }}
      last = j.token;
      status.textContent = j.error ? 'error' : 'live';
      status.classList.toggle('is-error', !!j.error);
    }}).catch(function(){{
      status.textContent = 'offline';
    }});
  }}
  poll();
  setInterval(poll, 600);
}})();
</script>
</body>
</html>
"""


ERROR_SHELL = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>preview error</title>
<style>
body{{font-family:ui-monospace,Menlo,Consolas,monospace;background:#1f1f1f;color:#eee;padding:2rem;line-height:1.55}}
h1{{color:#ff6b6b;font-size:1.2rem;margin:0 0 1rem 0}}
pre{{background:#111;padding:1rem;border-radius:6px;overflow:auto;white-space:pre-wrap}}
.bar{{background:#dc2626;color:#fff;padding:.4rem 1rem;margin:-2rem -2rem 1rem -2rem;font-size:.85rem}}
</style></head><body>
<div class="bar">compile error · {file}</div>
<h1>{kind}</h1>
<pre>{message}</pre>
<script>
setInterval(function(){{
  fetch('/__mtime__',{{cache:'no-store'}}).then(function(r){{return r.json();}}).then(function(j){{
    if(j.token && j.token !== '{token}'){{ location.reload(); }}
  }}).catch(function(){{}});
}}, 600);
</script>
</body></html>"""


BASE_CSS = """
:root {
  --content-max: 80vw;
  --text: #1a1a1a;
  --muted: #555;
  --bg: #fafaf7;
  --accent: #2563eb;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 18px;
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}
.omelet-preview-bar {
  display: flex;
  align-items: center;
  gap: .5rem;
  background: #1a1a1a;
  color: #eee;
  padding: .35rem 1rem;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: .78rem;
  position: sticky;
  top: 0;
  z-index: 100;
}
.omelet-preview-bar__dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #16a34a;
  box-shadow: 0 0 6px #16a34a;
}
.omelet-preview-bar__spacer { flex: 1; }
.omelet-preview-bar code { background: #333; padding: 1px 5px; border-radius: 3px; }
.omelet-preview-bar #omelet-preview-status.is-error { color: #ff6b6b; }
.gh-main { padding: 2.5rem 1rem 5rem 1rem; }
.gh-canvas { max-width: var(--content-max); width: 100%; margin: 0 auto; }
.gh-article-header { padding-bottom: 1.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid #e5e5e5; }
.gh-article-title {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 2.2rem;
  font-weight: 700;
  line-height: 1.2;
  margin: 0;
}
.gh-article-excerpt {
  font-size: 1.05rem;
  color: var(--muted);
  margin: .8rem 0 0 0;
}
.gh-content h1, .gh-content h2, .gh-content h3, .gh-content h4 {
  font-family: 'Inter', system-ui, sans-serif;
  font-weight: 700;
  line-height: 1.3;
  margin-top: 2.2rem;
}
.gh-content h2 { font-size: 1.55rem; }
.gh-content h3 { font-size: 1.2rem; }
.gh-content p { margin: 1rem 0; }
.gh-content a { color: var(--accent); }
.gh-content blockquote {
  border-left: 3px solid #c7c7c7;
  padding: .2rem 0 .2rem 1rem;
  margin: 1.2rem 0;
  color: #333;
  font-style: italic;
}
.gh-content code {
  font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace;
  font-size: .9em;
  background: #ececea;
  padding: 1px 5px;
  border-radius: 3px;
}
.gh-content pre {
  background: #1f2733;
  color: #e6e6e6;
  padding: 1rem 1.2rem;
  border-radius: 6px;
  overflow-x: auto;
  font-size: .88em;
  line-height: 1.55;
}
.gh-content pre code { background: transparent; padding: 0; color: inherit; }
.gh-content img { max-width: 100%; height: auto; border-radius: 6px; }
.gh-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 1.2rem 0;
  font-size: .92em;
}
.gh-content th, .gh-content td {
  border: 1px solid #d4d4d4;
  padding: .5rem .8rem;
  text-align: left;
}
.gh-content th { background: #f0f0ec; font-weight: 600; }
.gh-content hr { border: 0; border-top: 1px solid #d4d4d4; margin: 2rem 0; }
"""


def render_page(
    *,
    file_path: Path,
    theme_css_url: Optional[str],
    token: str,
) -> RenderOutput:
    suffix = file_path.suffix.lower()
    try:
        source = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _error("FileNotFound", f"{file_path} not found", file_path, token)

    if suffix not in (".mdx", ".md"):
        return _error(
            "UnsupportedExtension",
            f"Only .mdx and .md supported, got {suffix}",
            file_path,
            token,
        )

    try:
        cite_default = file_path.parent / "citations.yaml"
        cite_path = cite_default if cite_default.exists() else None
        result = compile_mdx_string(
            source,
            citations_path=cite_path,
            assets_dir=file_path.parent,
            slug=file_path.parent.name,
            strict=False,
        )
    except Exception as exc:
        return _error(type(exc).__name__, str(exc), file_path, token)

    fm = result.frontmatter or {}
    title = str(fm.get("title") or file_path.stem)
    excerpt = fm.get("description") or fm.get("custom_excerpt") or ""
    excerpt_block = (
        f'<p class="gh-article-excerpt is-body">{_html.escape(str(excerpt))}</p>'
        if excerpt
        else ""
    )

    theme_link = (
        f'<link rel="stylesheet" href="{theme_css_url}">' if theme_css_url else ""
    )

    page = SHELL.format(
        title=_html.escape(title),
        title_escaped=_html.escape(title),
        slug=_html.escape(file_path.name),
        body=result.html,
        excerpt_block=excerpt_block,
        theme_link=theme_link,
        base_css=BASE_CSS,
    )
    return RenderOutput(html=page, title=title)


def _error(kind: str, message: str, file_path: Path, token: str) -> RenderOutput:
    page = ERROR_SHELL.format(
        kind=_html.escape(kind),
        message=_html.escape(message),
        file=_html.escape(str(file_path)),
        token=_html.escape(token),
    )
    return RenderOutput(html=page, title=f"error: {file_path.name}", error=message)
