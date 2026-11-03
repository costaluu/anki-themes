"""Theme engine: loads theme files and turns them into CSS and Qt colors.

Pure Python (no aqt import) so it can be unit tested outside Anki.

A theme is a JSON file in ``themes/``::

    {"id": "flame", "name": "Flame", "description": "...",
     "tokens": {"light": {"canvas": "#fff"}, "dark": {"canvas": "#000"}},
     "extra_css": "", "extra_qss": ""}

Token names are Anki's own CSS variable names without the leading ``--``
(``canvas``, ``fg-subtle``, ``button-primary-bg``...). Anki generates its Qt
palette and every web page from the same table (``_aqt.colors``), so overriding
that table plus the CSS variables restyles the whole application.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

THEMES_DIR = Path(__file__).resolve().parent / "themes"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_TOKEN_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Colors only: hex, named, rgb()/rgba()/hsl()/hsla() with numbers, %, commas, dots.
_VALUE_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z]+|(rgb|rgba|hsl|hsla)\([0-9a-zA-Z.,%\s/-]+\))$")
# extra_css / extra_qss must not be able to close the <style> tag or load things.
_FORBIDDEN_CSS = re.compile(r"</|<!--|@import|url\s*\(|expression\s*\(|javascript:", re.I)

MODES = ("light", "dark")


class ThemeError(ValueError):
    """Raised when a theme file is invalid."""


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    description: str
    tokens: dict[str, dict[str, str]]
    extra_css: str = ""
    extra_qss: str = ""
    path: Path | None = field(default=None, compare=False)


def _check_css_text(label: str, text: Any) -> str:
    if not isinstance(text, str):
        raise ThemeError(f"{label} must be a string")
    if _FORBIDDEN_CSS.search(text):
        raise ThemeError(f"{label} contains a forbidden construct")
    return text


def parse_theme(data: Any, path: Path | None = None) -> Theme:
    """Validate raw JSON data and build a Theme. Raises ThemeError."""
    if not isinstance(data, dict):
        raise ThemeError("theme must be a JSON object")
    tid = data.get("id")
    if not isinstance(tid, str) or not _ID_RE.match(tid):
        raise ThemeError(f"invalid theme id: {tid!r}")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ThemeError(f"{tid}: missing name")
    tokens = data.get("tokens")
    if not isinstance(tokens, dict) or not set(tokens) <= set(MODES) or not tokens:
        raise ThemeError(f"{tid}: tokens must have 'light' and/or 'dark'")
    clean: dict[str, dict[str, str]] = {}
    for mode, table in tokens.items():
        if not isinstance(table, dict):
            raise ThemeError(f"{tid}: tokens.{mode} must be an object")
        clean[mode] = {}
        for key, value in table.items():
            if not _TOKEN_RE.match(key):
                raise ThemeError(f"{tid}: invalid token name {key!r}")
            if not isinstance(value, str) or not _VALUE_RE.match(value.strip()):
                raise ThemeError(f"{tid}: invalid color for {mode}.{key}: {value!r}")
            clean[mode][key] = value.strip()
    return Theme(
        id=tid,
        name=name.strip(),
        description=str(data.get("description", "")),
        tokens=clean,
        extra_css=_check_css_text(f"{tid}: extra_css", data.get("extra_css", "")),
        extra_qss=_check_css_text(f"{tid}: extra_qss", data.get("extra_qss", "")),
        path=path,
    )


def load_themes(directory: Path = THEMES_DIR) -> tuple[dict[str, Theme], dict[str, str]]:
    """Load every ``*.json`` in directory. Returns (themes, errors-by-filename).

    A broken theme file never prevents the others from loading.
    """
    themes: dict[str, Theme] = {}
    errors: dict[str, str] = {}
    for p in sorted(Path(directory).glob("*.json")):
        try:
            theme = parse_theme(json.loads(p.read_text(encoding="utf-8")), p)
        except (OSError, ValueError) as exc:  # ThemeError is a ValueError
            errors[p.name] = str(exc)
            continue
        if theme.id in themes:
            errors[p.name] = f"duplicate theme id {theme.id!r}"
            continue
        themes[theme.id] = theme
    return themes, errors


# --------------------------------------------------------------------- web CSS

def build_css(theme: Theme) -> str:
    """CSS that overrides Anki's color variables.

    Anki defines them on ``:root`` (light) and ``:root.night-mode`` (dark).
    ``html:root`` is more specific, so ours wins regardless of load order.
    """
    parts: list[str] = []
    selectors = {"light": "html:root", "dark": "html:root.night-mode"}
    for mode in MODES:
        table = theme.tokens.get(mode)
        if not table:
            continue
        decls = ";".join(f"--{k}:{v}" for k, v in table.items())
        parts.append(f"{selectors[mode]}{{{decls}}}")
    if theme.extra_css:
        parts.append(theme.extra_css)
    return "\n".join(parts)


def style_tag(theme: Theme) -> str:
    return f'<style id="anki-themes">{build_css(theme)}</style>'


def inject_js(theme: Theme) -> str:
    """JS that installs (or replaces) the style tag in an already loaded page."""
    css = json.dumps(build_css(theme))
    return (
        "(function(){var s=document.getElementById('anki-themes');"
        "if(!s){s=document.createElement('style');s.id='anki-themes';"
        "(document.head||document.documentElement).appendChild(s);}"
        f"s.textContent={css};}})();"
    )


def remove_js() -> str:
    return "var s=document.getElementById('anki-themes');if(s){s.remove();}"


# -------------------------------------------------------------------- Qt colors

def token_to_const(token: str) -> str:
    """'canvas-elevated' -> 'CANVAS_ELEVATED' (name in _aqt.colors)."""
    return token.upper().replace("-", "_")


class QtColors:
    """Applies a theme to Anki's color table and can restore the originals."""

    def __init__(self, colors_module: Any):
        self._m = colors_module
        self._orig: dict[tuple[str, str], str] = {}

    def apply(self, theme: Theme | None) -> list[str]:
        """Restore defaults, then apply ``theme``. Returns unknown token names."""
        self.restore()
        unknown: list[str] = []
        if theme is None:
            return unknown
        for mode, table in theme.tokens.items():
            for token, value in table.items():
                entry = getattr(self._m, token_to_const(token), None)
                if not isinstance(entry, dict) or mode not in entry:
                    if token not in unknown:
                        unknown.append(token)
                    continue
                self._orig.setdefault((token_to_const(token), mode), entry[mode])
                entry[mode] = value
        return unknown

    def restore(self) -> None:
        for (const, mode), value in self._orig.items():
            getattr(self._m, const)[mode] = value
        self._orig.clear()
