"""Themes for Anki: switchable color themes for the whole application.

Everything that touches Anki lives here; the logic is in engine.py.
"""
from __future__ import annotations

import sys

try:
    from aqt import colors, gui_hooks, mw
except ImportError:  # imported outside Anki (tests, tooling)
    mw = None

if mw is not None:
    from aqt.qt import QAction, QActionGroup, QMenu
    from aqt.utils import tooltip

    from . import engine

    ADDON = __name__.split(".")[0]
    THEMES, ERRORS = engine.load_themes()
    QT = engine.QtColors(colors)

    def _log(msg: str) -> None:
        print(f"[themes] {msg}", file=sys.stderr)

    for _file, _err in ERRORS.items():
        _log(f"ignored {_file}: {_err}")

    def _config() -> dict:
        return mw.addonManager.getConfig(ADDON) or {}

    def current() -> engine.Theme | None:
        return THEMES.get(_config().get("theme", ""))

    def apply_qt() -> None:
        unknown = QT.apply(current())
        if unknown:
            _log("tokens unknown to this Anki version: " + ", ".join(unknown))

    def restyle() -> None:
        """Make Anki rebuild its Qt palette and stylesheet with the new colors."""
        try:
            from aqt.theme import theme_manager

            theme_manager._current_widget_style = None  # forces apply_style to run
            theme_manager.apply_style()
        except Exception as exc:  # best effort: a restart always works
            _log(f"live restyle failed ({exc}); restart Anki to apply")

    def _main_webviews() -> list:
        out = []
        for name in ("web", "bottomWeb"):
            w = getattr(mw, name, None)
            if w is not None:
                out.append(w)
        toolbar = getattr(mw, "toolbar", None)
        if toolbar is not None and getattr(toolbar, "web", None) is not None:
            out.append(toolbar.web)
        return out

    def refresh_webviews() -> None:
        theme = current()
        js = engine.inject_js(theme) if theme else engine.remove_js()
        for w in _main_webviews():
            try:
                w.eval(js)
            except Exception as exc:
                _log(f"webview refresh failed: {exc}")

    # ---------------------------------------------------------------- hooks
    def on_will_set_content(web_content, _context) -> None:
        theme = current()
        if theme:
            web_content.head += engine.style_tag(theme)

    def on_inject_style(webview) -> None:
        theme = current()
        if theme:
            webview.eval(engine.inject_js(theme))

    def on_style_did_init(buf: str) -> str:
        theme = current()
        return buf + "\n" + theme.extra_qss if theme and theme.extra_qss else buf

    gui_hooks.webview_will_set_content.append(on_will_set_content)
    gui_hooks.webview_did_inject_style_into_page.append(on_inject_style)
    gui_hooks.style_did_init.append(on_style_did_init)

    # Qt colors must be patched before Anki builds its palette.
    apply_qt()
    gui_hooks.profile_did_open.append(restyle)

    # ----------------------------------------------------------------- menu
    def set_theme(theme_id: str) -> None:
        cfg = _config()
        cfg["theme"] = theme_id
        mw.addonManager.writeConfig(ADDON, cfg)
        apply_qt()
        restyle()
        refresh_webviews()
        try:
            mw.reset()
        except Exception:
            pass
        name = THEMES[theme_id].name if theme_id in THEMES else "padrão do Anki"
        tooltip(f"Tema: {name}. Janelas já abertas (navegador, editor) mostram o novo tema ao reabrir.")

    def build_menu() -> None:
        menu = QMenu("Temas", mw)
        group = QActionGroup(menu)
        group.setExclusive(True)
        active = _config().get("theme", "")
        entries = [("", "Padrão do Anki")] + [(t.id, t.name) for t in THEMES.values()]
        for theme_id, label in entries:
            action = QAction(label, menu, checkable=True)
            action.setChecked(theme_id == active)
            action.triggered.connect(lambda _checked=False, tid=theme_id: set_theme(tid))
            group.addAction(action)
            menu.addAction(action)
        mw.form.menuTools.addMenu(menu)

    build_menu()
