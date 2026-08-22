"""
Widget render checker: build an isolated harness page (theme built CSS + widget
markup, mirroring how <Widget> inlines the file into a figure.omelet-widget),
serve it locally, load it in headless Chromium, and probe execution state.

Catches the failure modes that otherwise only surface after publish:
- script throws before drawing (missing getElementById target, console errors)
- canvas stays blank (zero non-white/non-transparent pixels)
- CSS from the theme silently overriding widget styles (computed style dump)

Playwright is an optional dependency: `pip install "omelet[widget]"` then
`python -m playwright install chromium`.
"""

from __future__ import annotations

import json
import re
import socket
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SETTLE_MS_DEFAULT = 900

THEME_CSS_CANDIDATES = [
    Path.home() / "github" / "omelet.tech-template" / "assets" / "built" / "screen.css",
    Path.home() / "github" / "omelet.tech-template" / "assets" / "css" / "screen.css",
    Path.home() / "git" / "omelet.tech-template" / "assets" / "built" / "screen.css",
    Path.home() / "git" / "omelet.tech-template" / "assets" / "css" / "screen.css",
]

ID_REF_RE = re.compile(r"""getElementById\(\s*["']([^"']+)["']""")
DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>", re.IGNORECASE)
XML_DECL_RE = re.compile(r"<\?xml[^>]*\?>")

HARNESS_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>widget-check harness</title>
<style>
{theme_css}
</style>
</head>
<body>
<main class="gh-content" style="max-width: 760px; margin: 0 auto; padding: 24px;">
<figure class="omelet-widget">
{widget_markup}
</figure>
</main>
</body>
</html>
"""

PROBE_JS = """async ([settleMs, ids]) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let rafCount = 0;
  const tick = () => { rafCount++; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  await sleep(settleMs);

  const out = {
    rafCount,
    visibilityState: document.visibilityState,
    hidden: document.hidden,
    missingIds: ids.filter((id) => document.getElementById(id) === null),
    canvases: [],
  };

  for (const c of document.querySelectorAll("canvas")) {
    const info = { width: c.width, height: c.height, id: c.id || null };
    const cs = getComputedStyle(c);
    info.computed = {
      display: cs.display,
      visibility: cs.visibility,
      border: cs.border,
      borderRadius: cs.borderRadius,
      background: cs.backgroundColor,
      padding: cs.padding,
    };
    const wrap = c.parentElement;
    if (wrap) {
      const ws = getComputedStyle(wrap);
      info.wrapper = {
        tag: wrap.tagName,
        class: typeof wrap.className === "string" ? wrap.className : "",
        border: ws.border,
        borderRadius: ws.borderRadius,
        background: ws.backgroundColor,
      };
    }
    try {
      const ctx = c.getContext("2d");
      if (!ctx) {
        info.probe = "no-2d-context";
      } else {
        const data = ctx.getImageData(0, 0, c.width, c.height).data;
        let nonBlank = 0;
        for (let i = 0; i < data.length; i += 4) {
          const a = data[i + 3];
          if (a > 0 && !(data[i] > 250 && data[i + 1] > 250 && data[i + 2] > 250)) nonBlank++;
        }
        info.nonBlankPixels = nonBlank;
      }
    } catch (e) {
      info.probe = "tainted: " + e.message;
    }
    out.canvases.push(info);
  }
  return out;
}"""


def resolve_theme_css(override: Path | None) -> Path | None:
    if override is not None:
        return override
    for candidate in THEME_CSS_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def build_harness(widget_src: str, theme_css: str) -> str:
    markup = XML_DECL_RE.sub("", DOCTYPE_RE.sub("", widget_src)).strip()
    return HARNESS_TEMPLATE.format(theme_css=theme_css, widget_markup=markup)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def probe_harness(html: str, ids: list[str], settle_ms: int) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "widget check cần playwright: pip install \"omelet[widget]\" "
            "rồi python -m playwright install chromium"
        ) from e

    console_errors: list[str] = []
    page_errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="omelet-widget-") as tmp:
        Path(tmp, "index.html").write_text(html, encoding="utf-8")
        server = ThreadingHTTPServer(
            ("127.0.0.1", _free_port()), partial(_QuietHandler, directory=tmp)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
                )
                page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                page.goto(url, wait_until="load")
                result = page.evaluate(PROBE_JS, [settle_ms, ids])
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)

    result["consoleErrors"] = console_errors
    result["pageErrors"] = page_errors
    return result


def check_widget(
    file: Path,
    theme_override: Path | None = None,
    settle_ms: int = SETTLE_MS_DEFAULT,
    allow_blank_canvas: bool = False,
) -> dict:
    widget_src = file.read_text(encoding="utf-8")
    ids = sorted(set(ID_REF_RE.findall(widget_src)))

    theme_path = resolve_theme_css(theme_override)
    theme_css = theme_path.read_text(encoding="utf-8") if theme_path else ""

    html = build_harness(widget_src, theme_css)
    probe = probe_harness(html, ids, settle_ms)

    errors: list[str] = []
    warnings: list[str] = []

    for msg in probe["pageErrors"]:
        errors.append(f"page error: {msg}")
    for msg in probe["consoleErrors"]:
        errors.append(f"console error: {msg}")
    for missing in probe["missingIds"]:
        errors.append(f'getElementById("{missing}") trả null - script sẽ throw trước khi vẽ')
    if probe["rafCount"] == 0:
        errors.append("requestAnimationFrame không chạy frame nào")
    for c in probe["canvases"]:
        label = f'canvas#{c["id"]}' if c["id"] else "canvas"
        if c.get("probe", "").startswith("tainted"):
            warnings.append(f"{label}: canvas bị taint, không đọc được pixel ({c['probe']})")
        elif c.get("nonBlankPixels") == 0:
            msg = f"{label} ({c['width']}x{c['height']}): 0 pixel khác trắng/transparent - canvas trắng"
            if allow_blank_canvas:
                warnings.append(msg)
            else:
                errors.append(msg)

    return {
        "file": str(file),
        "theme_css": str(theme_path) if theme_path else None,
        "theme_found": theme_path is not None,
        "ids_referenced": ids,
        "settle_ms": settle_ms,
        "probe": probe,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def print_report(report: dict) -> None:
    import click

    status = click.style("OK", fg="green", bold=True) if report["ok"] else click.style("FAIL", fg="red", bold=True)
    click.echo(f"{status} {report['file']}")
    if not report["theme_found"]:
        click.echo(click.style("  warn: không tìm thấy theme screen.css, probe chạy không có theme CSS", fg="yellow"))
    else:
        click.echo(f"  theme: {report['theme_css']}")

    probe = report["probe"]
    click.echo(f"  raf frames: {probe['rafCount']} | visibility: {probe['visibilityState']}")
    for c in probe["canvases"]:
        label = f'canvas#{c["id"]}' if c["id"] else "canvas"
        pixels = c.get("nonBlankPixels", "?")
        click.echo(f"  {label} {c['width']}x{c['height']} non-blank pixels: {pixels}")
        comp = c.get("computed", {})
        click.echo(f"    computed: border={comp.get('border')} radius={comp.get('borderRadius')} bg={comp.get('background')}")
    for w in report["warnings"]:
        click.echo(click.style(f"  warn: {w}", fg="yellow"))
    for e in report["errors"]:
        click.echo(click.style(f"  error: {e}", fg="red"))
    if not probe["canvases"]:
        click.echo("  (không có canvas nào trong widget)")


def report_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
