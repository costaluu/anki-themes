"""Theme engine: loads theme files and turns them into CSS and Qt colors.

Pure Python (no aqt import) so it can be unit tested outside Anki.

A theme is a JSON file in ``themes/``. It can be written two ways (or mixed):

1. ``tokens``: Anki's own CSS variable names without the ``--``
   (``canvas``, ``fg-subtle``, ``button-primary-bg``...), one value each.
2. ``palette``: a short list of *roles* per mode (``bg``, ``fg``, ``accent``...).
   ``ROLE_MAP`` expands them into every token; explicit ``tokens`` win.

    {"id": "x", "name": "X", "palette": {"dark": {"bg": "#101010", ...}},
     "tokens": {"dark": {"border-focus": "#f00"}}}

Role values may be ``#rgb``/``#rrggbb``; token values may also reference a role
as ``$role`` or ``$role@0.4`` (the same color with 40% alpha).

Anki generates its Qt palette and every web page from one table
(``_aqt.colors``), so overriding that table plus the CSS variables restyles the
whole application.
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

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_REF_RE = re.compile(r"^\$([a-z][a-z0-9_]*)(?:@([0-9]*\.?[0-9]+))?$")

# token -> expression over palette roles ("$role" or "$role@alpha")
ROLE_MAP: dict[str, str] = {
    "canvas": "$bg",
    "canvas-elevated": "$bg_elevated",
    "canvas-inset": "$bg_inset",
    "canvas-overlay": "$bg_overlay",
    "canvas-code": "$bg_code",
    "canvas-glass": "$bg_elevated@0.4",
    "fg": "$fg",
    "fg-subtle": "$fg_subtle",
    "fg-disabled": "$fg_disabled",
    "fg-faint": "$fg_faint",
    "fg-link": "$link",
    "border": "$border",
    "border-subtle": "$border_subtle",
    "border-strong": "$border_strong",
    "border-focus": "$accent",
    "button-bg": "$button",
    "button-gradient-start": "$button_hi",
    "button-gradient-end": "$button",
    "button-hover-border": "$accent",
    "button-disabled": "$border@0.5",
    "button-primary-bg": "$primary_dim",
    "button-primary-gradient-start": "$primary",
    "button-primary-gradient-end": "$primary_dim",
    "button-primary-disabled": "$primary@0.4",
    "scrollbar-bg": "$scrollbar",
    "scrollbar-bg-hover": "$scrollbar_hover",
    "scrollbar-bg-active": "$scrollbar_active",
    "shadow": "$shadow",
    "shadow-inset": "$shadow",
    "shadow-subtle": "$border_strong",
    "shadow-focus": "$accent",
    "accent-card": "$accent",
    "accent-note": "$note",
    "accent-danger": "$danger",
    "state-new": "$new",
    "state-learn": "$learn",
    "state-review": "$review",
    "highlight-bg": "$highlight@0.4",
    "highlight-fg": "$on_highlight",
    "selected-bg": "$accent@0.25",
    "selected-fg": "$fg",
}

REQUIRED_ROLES = (
    "bg", "bg_elevated", "bg_inset", "bg_overlay", "bg_code",
    "fg", "fg_subtle", "fg_disabled", "fg_faint",
    "border", "border_subtle", "border_strong",
    "button", "button_hi", "accent", "accent_dim", "link",
    "scrollbar", "scrollbar_hover", "scrollbar_active", "shadow",
    "danger", "new", "learn", "review", "note",
)
# optional role -> role it falls back to
ROLE_FALLBACKS = {"primary": "accent", "primary_dim": "accent_dim",
                  "highlight": "accent", "on_highlight": "fg"}


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


def _rgba(hex_color: str, alpha: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    a = float(alpha)
    if not 0 <= a <= 1:
        raise ThemeError(f"alpha out of range: {alpha}")
    return f"rgba({r}, {g}, {b}, {a:g})"


def resolve_ref(expr: str, roles: dict[str, str]) -> str | None:
    """Resolve ``$role`` / ``$role@alpha``. Returns None if expr is not a reference."""
    m = _REF_RE.match(expr.strip())
    if not m:
        return None
    role, alpha = m.group(1), m.group(2)
    value = roles.get(role)
    if value is None:
        raise ThemeError(f"unknown palette role: {role}")
    return _rgba(value, alpha) if alpha is not None else value


def expand_palette(tid: str, mode: str, raw: Any) -> dict[str, str]:
    """Validate one mode's palette and expand it into tokens via ROLE_MAP."""
    if not isinstance(raw, dict):
        raise ThemeError(f"{tid}: palette.{mode} must be an object")
    roles: dict[str, str] = {}
    for key, value in raw.items():
        if not re.match(r"^[a-z][a-z0-9_]*$", key):
            raise ThemeError(f"{tid}: invalid role name {key!r}")
        if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
            raise ThemeError(f"{tid}: palette.{mode}.{key} must be #rgb or #rrggbb, got {value!r}")
        roles[key] = value.strip()
    missing = [r for r in REQUIRED_ROLES if r not in roles]
    if missing:
        raise ThemeError(f"{tid}: palette.{mode} is missing roles: {', '.join(missing)}")
    for opt, fallback in ROLE_FALLBACKS.items():
        roles.setdefault(opt, roles[fallback])
    return {token: resolve_ref(expr, roles) for token, expr in ROLE_MAP.items()}


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
    raw_tokens = data.get("tokens", {})
    raw_palette = data.get("palette", {})
    for label, section in (("tokens", raw_tokens), ("palette", raw_palette)):
        if not isinstance(section, dict) or not set(section) <= set(MODES):
            raise ThemeError(f"{tid}: {label} may only have 'light' and/or 'dark'")
    if not raw_tokens and not raw_palette:
        raise ThemeError(f"{tid}: needs 'tokens' and/or 'palette'")
    clean: dict[str, dict[str, str]] = {}
    for mode, raw in raw_palette.items():
        clean[mode] = expand_palette(tid, mode, raw)
    for mode, table in raw_tokens.items():
        if not isinstance(table, dict):
            raise ThemeError(f"{tid}: tokens.{mode} must be an object")
        roles = {k: v for k, v in raw_palette.get(mode, {}).items() if isinstance(v, str)}
        for opt, fallback in ROLE_FALLBACKS.items():
            if fallback in roles:
                roles.setdefault(opt, roles[fallback])
        out = clean.setdefault(mode, {})
        for key, value in table.items():
            if not _TOKEN_RE.match(key):
                raise ThemeError(f"{tid}: invalid token name {key!r}")
            if not isinstance(value, str):
                raise ThemeError(f"{tid}: invalid color for {mode}.{key}: {value!r}")
            ref = resolve_ref(value, roles)
            value = ref if ref is not None else value.strip()
            if not _VALUE_RE.match(value):
                raise ThemeError(f"{tid}: invalid color for {mode}.{key}: {value!r}")
            out[key] = value
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
