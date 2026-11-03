"""Loads addon/__init__.py against a stubbed `aqt` to check the hook wiring."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ADDON = Path(__file__).resolve().parent.parent / "addon"


class Hook:
    def __init__(self):
        self.fns = []

    def append(self, fn):
        self.fns.append(fn)


def load_addon(config):
    colors = types.SimpleNamespace(
        CANVAS={"comment": "", "light": "#f5f5f5", "dark": "#2c2c2c"},
        FG={"comment": "", "light": "#020202", "dark": "#fcfcfc"},
    )
    hooks = types.SimpleNamespace(
        webview_will_set_content=Hook(), webview_did_inject_style_into_page=Hook(),
        style_did_init=Hook(), profile_did_open=Hook())
    store = {"cfg": dict(config)}
    mw = mock.MagicMock()
    mw.addonManager.getConfig.side_effect = lambda _n: dict(store["cfg"])
    mw.addonManager.writeConfig.side_effect = lambda _n, c: store.update(cfg=dict(c))
    tm = types.SimpleNamespace(_current_widget_style="x", apply_style=mock.MagicMock())
    stubs = {
        "aqt": types.SimpleNamespace(colors=colors, gui_hooks=hooks, mw=mw),
        "aqt.qt": types.SimpleNamespace(QAction=mock.MagicMock(), QActionGroup=mock.MagicMock(),
                                        QMenu=mock.MagicMock()),
        "aqt.utils": types.SimpleNamespace(tooltip=mock.MagicMock()),
        "aqt.theme": types.SimpleNamespace(theme_manager=tm),
    }
    spec = importlib.util.spec_from_file_location(
        "anki_themes", ADDON / "__init__.py", submodule_search_locations=[str(ADDON)])
    mod = importlib.util.module_from_spec(spec)
    patcher = mock.patch.dict(sys.modules, stubs)
    patcher.start()  # stubs stay active: the add-on imports aqt.theme lazily
    sys.modules["anki_themes"] = mod
    spec.loader.exec_module(mod)
    return mod, colors, hooks, mw, tm, store, patcher


class WiringTests(unittest.TestCase):
    def load(self, config):
        *rest, patcher = load_addon(config)
        self.addCleanup(patcher.stop)
        return rest

    def test_enabled_theme_patches_colors_and_registers_hooks(self):
        mod, colors, hooks, mw, tm, _ = self.load({"theme": "flame"})
        self.assertEqual(colors.CANVAS["dark"], "#1b1210")
        self.assertEqual(len(hooks.webview_will_set_content.fns), 1)
        self.assertEqual(len(hooks.webview_did_inject_style_into_page.fns), 1)
        self.assertEqual(len(hooks.style_did_init.fns), 1)
        wc = types.SimpleNamespace(head="<head>")
        hooks.webview_will_set_content.fns[0](wc, None)
        self.assertIn('id="anki-themes"', wc.head)
        self.assertIn("--canvas:#1b1210", wc.head)
        web = mock.MagicMock()
        hooks.webview_did_inject_style_into_page.fns[0](web)
        web.eval.assert_called_once()
        mw.form.menuTools.addAction.assert_called_once()
        mw.addonManager.setConfigAction.assert_called_once()

    def test_disabled_theme_leaves_everything_alone(self):
        mod, colors, hooks, *_ = self.load({"theme": ""})
        self.assertEqual(colors.CANVAS["dark"], "#2c2c2c")
        wc = types.SimpleNamespace(head="<head>")
        hooks.webview_will_set_content.fns[0](wc, None)
        self.assertEqual(wc.head, "<head>")
        self.assertEqual(hooks.style_did_init.fns[0]("QSS"), "QSS")

    def test_unknown_theme_in_config_is_safe(self):
        _, colors, hooks, *_ = self.load({"theme": "does-not-exist"})
        self.assertEqual(colors.CANVAS["dark"], "#2c2c2c")

    def test_set_theme_switches_persists_and_restyles(self):
        mod, colors, hooks, mw, tm, store = self.load({"theme": ""})
        mod.set_theme("flame")
        self.assertEqual(store["cfg"]["theme"], "flame")
        self.assertEqual(colors.CANVAS["dark"], "#1b1210")
        tm.apply_style.assert_called()
        self.assertIsNone(tm._current_widget_style)
        mw.web.eval.assert_called()
        mod.set_theme("")
        self.assertEqual(colors.CANVAS["dark"], "#2c2c2c")
        self.assertIn("remove()", mw.web.eval.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
