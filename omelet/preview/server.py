from __future__ import annotations

import json
import mimetypes
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from .render import render_page


STATIC_DIR = Path(__file__).parent / "static"


class PreviewServer:
    def __init__(
        self,
        *,
        file_path: Path,
        host: str,
        port: int,
        theme_css_path: Optional[Path],
        watch_components: bool,
    ):
        self.file_path = file_path.resolve()
        self.host = host
        self.port = port
        self.theme_css_path = theme_css_path.resolve() if theme_css_path else None
        self.watch_components = watch_components
        self._stop = threading.Event()
        self._last_token: Optional[str] = None
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

    def watched_paths(self) -> list[Path]:
        paths = [self.file_path]
        cite = self.file_path.parent / "citations.yaml"
        if cite.exists():
            paths.append(cite)
        if self.theme_css_path and self.theme_css_path.exists():
            paths.append(self.theme_css_path)
        if self.watch_components:
            comp_dir = Path(__file__).parent.parent / "mdx" / "components"
            if comp_dir.exists():
                paths.extend(sorted(comp_dir.glob("*.py")))
        return paths

    def mtime_token(self) -> str:
        parts = []
        for p in self.watched_paths():
            try:
                parts.append(f"{p.name}:{p.stat().st_mtime_ns}")
            except OSError:
                parts.append(f"{p.name}:missing")
        return "|".join(parts)


def start_server(
    *,
    file_path: Path,
    host: str = "0.0.0.0",
    port: int = 4321,
    theme_css_path: Optional[Path] = None,
    open_browser: bool = True,
    watch_components: bool = True,
) -> None:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    state = PreviewServer(
        file_path=file_path,
        host=host,
        port=port,
        theme_css_path=theme_css_path,
        watch_components=watch_components,
    )

    handler_cls = _make_handler(state)
    port = _pick_port(host, port)
    state.port = port
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"omelet preview · {file_path}", flush=True)
    print(f"  local     http://127.0.0.1:{port}/", flush=True)
    if host == "0.0.0.0":
        lan_ip = _detect_lan_ip()
        if lan_ip:
            print(f"  network   http://{lan_ip}:{port}/", flush=True)
    elif host not in ("127.0.0.1", "localhost"):
        print(f"  bind      http://{host}:{port}/", flush=True)
    for p in state.watched_paths():
        print(f"  watching  {p}", flush=True)

    open_url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(open_url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping preview")
    finally:
        server.server_close()


def _pick_port(host: str, preferred: int) -> int:
    for candidate in [preferred, *range(preferred + 1, preferred + 20)]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, candidate))
                return candidate
        except OSError:
            continue
    raise RuntimeError(f"no free port near {preferred}")


def _detect_lan_ip() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _make_handler(state: PreviewServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)

            if path == "/" or path == "/index.html":
                self._serve_page()
                return
            if path == "/__mtime__":
                self._serve_mtime()
                return
            if path.startswith("/__assets__/"):
                self._serve_static(path[len("/__assets__/"):])
                return
            if path == "/__theme__.css":
                self._serve_theme_css()
                return
            self._serve_relative(path.lstrip("/"))

        def _serve_page(self):
            theme_url = "/__theme__.css" if state.theme_css_path else None
            out = render_page(
                file_path=state.file_path,
                theme_css_url=theme_url,
                token=state.mtime_token(),
            )
            body = out.html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _serve_mtime(self):
            tok = state.mtime_token()
            with state._lock:
                if tok != state._last_token:
                    out = render_page(
                        file_path=state.file_path, theme_css_url=None, token=tok
                    )
                    state._last_token = tok
                    state._last_error = out.error
                err = state._last_error
            payload = {"token": tok, "error": err}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _serve_static(self, name: str):
            target = (STATIC_DIR / name).resolve()
            try:
                target.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_error(403)
                return
            self._send_file(target)

        def _serve_theme_css(self):
            if not state.theme_css_path or not state.theme_css_path.exists():
                self.send_error(404)
                return
            self._send_file(state.theme_css_path)

        def _serve_relative(self, rel: str):
            base = state.file_path.parent.resolve()
            target = (base / rel).resolve()
            try:
                target.relative_to(base)
            except ValueError:
                self.send_error(403)
                return
            if not target.exists() or not target.is_file():
                self.send_error(404)
                return
            self._send_file(target)

        def _send_file(self, target: Path):
            try:
                data = target.read_bytes()
            except OSError:
                self.send_error(404)
                return
            ctype, _ = mimetypes.guess_type(str(target))
            if not ctype:
                ctype = "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler
