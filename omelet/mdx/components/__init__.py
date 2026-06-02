from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..citations import CiteRegistry


RenderFn = Callable[["RenderContext", dict, str], str]


@dataclass
class RenderContext:
    citations: CiteRegistry
    frontmatter: dict
    assets_dir: Optional[Path] = None
    slug: str = ""
    components_strict: bool = True
    md_renderer: Optional[Callable[[str], str]] = None
    parent_chain: list[str] = field(default_factory=list)

    def render_md(self, text: str) -> str:
        if self.md_renderer is None:
            return text
        return self.md_renderer(text).strip()


_REGISTRY: dict[str, RenderFn] = {}
_DISCOVERED = False


def register(name: str, fn: RenderFn) -> None:
    _REGISTRY[name] = fn


def get(name: str) -> Optional[RenderFn]:
    _ensure_discovered()
    return _REGISTRY.get(name)


def names() -> list[str]:
    _ensure_discovered()
    return sorted(_REGISTRY.keys())


def _ensure_discovered() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    package_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(package_path)]):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{info.name}")


class ComponentError(Exception):
    pass


def require_prop(name: str, props: dict, component: str) -> object:
    if name not in props:
        raise ComponentError(
            f"<{component}> missing required prop {name!r}"
        )
    return props[name]


def opt_prop(name: str, props: dict, default: object = "") -> object:
    return props.get(name, default)


def html_escape(s: object) -> str:
    import html as _h
    return _h.escape(str(s), quote=True)
