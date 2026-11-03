import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))
import engine  # noqa: E402


def fake_colors():
    m = types.SimpleNamespace()
    m.CANVAS = {"comment": "x", "light": "#f5f5f5", "dark": "#2c2c2c"}
    m.FG_SUBTLE = {"comment": "x", "light": "#737373", "dark": "#858585"}
    return m


def minimal(**over):
    d = {"id": "t", "name": "T", "tokens": {"light": {"canvas": "#fff"}, "dark": {"canvas": "#000"}}}
    d.update(over)
    return d


class ParseTests(unittest.TestCase):
    def test_flame_is_valid_and_complete(self):
        themes, errors = engine.load_themes()
        self.assertEqual(errors, {})
        flame = themes["flame"]
        self.assertEqual(set(flame.tokens), {"light", "dark"})
        self.assertEqual(set(flame.tokens["light"]), set(flame.tokens["dark"]))
        self.assertGreaterEqual(len(flame.tokens["dark"]), 40)

    def test_rejects_bad_input(self):
        bad = [
            minimal(id="Bad Id"),
            minimal(name=""),
            minimal(tokens={}),
            minimal(tokens={"sepia": {"canvas": "#fff"}}),
            minimal(tokens={"light": {"canvas": "red; background:url(x)"}}),
            minimal(tokens={"light": {"Canvas!": "#fff"}}),
            minimal(tokens={"light": {"canvas": 5}}),
            minimal(extra_css="</style><script>alert(1)</script>"),
            minimal(extra_css="@import 'http://x/y.css';"),
            minimal(extra_css="a{background:url(http://x)}"),
        ]
        for data in bad:
            with self.assertRaises(engine.ThemeError, msg=str(data)):
                engine.parse_theme(data)
        with self.assertRaises(engine.ThemeError):
            engine.parse_theme([])

    def test_accepts_color_forms(self):
        ok = {"a": "#fff", "b": "#ffffff80", "c": "white", "d": "rgba(255, 250, 240, 0.5)",
              "e": "rgb(25.1%, 25%, 25%)", "f": "hsl(10 50% 50%)"}
        t = engine.parse_theme(minimal(tokens={"light": ok}))
        self.assertEqual(len(t.tokens["light"]), 6)

    def test_broken_file_does_not_block_others(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a_good.json").write_text(json.dumps(minimal(id="good")))
            (Path(d) / "bad.json").write_text("{not json")
            (Path(d) / "z_dup.json").write_text(json.dumps(minimal(id="good")))
            themes, errors = engine.load_themes(Path(d))
        self.assertEqual(list(themes), ["good"])
        self.assertEqual(set(errors), {"bad.json", "z_dup.json"})


def full_palette(**over):
    p = {r: "#123456" for r in engine.REQUIRED_ROLES}
    p.update(bg="#101010", fg="#eeeeee", accent="#ff8800", accent_dim="#cc6600")
    p.update(over)
    return p


class PaletteTests(unittest.TestCase):
    def test_palette_expands_to_every_token_in_role_map(self):
        t = engine.parse_theme({"id": "p", "name": "P", "palette": {"dark": full_palette()}})
        self.assertEqual(set(t.tokens["dark"]), set(engine.ROLE_MAP))
        self.assertEqual(t.tokens["dark"]["canvas"], "#101010")
        self.assertEqual(t.tokens["dark"]["fg"], "#eeeeee")

    def test_alpha_references(self):
        t = engine.parse_theme({"id": "p", "name": "P", "palette": {"dark": full_palette()}})
        self.assertEqual(t.tokens["dark"]["selected-bg"], "rgba(255, 136, 0, 0.25)")
        self.assertEqual(t.tokens["dark"]["highlight-bg"], "rgba(255, 136, 0, 0.4)")

    def test_optional_roles_fall_back(self):
        t = engine.parse_theme({"id": "p", "name": "P", "palette": {"dark": full_palette()}})
        self.assertEqual(t.tokens["dark"]["button-primary-gradient-start"], "#ff8800")  # primary -> accent
        self.assertEqual(t.tokens["dark"]["button-primary-bg"], "#cc6600")  # primary_dim -> accent_dim
        t2 = engine.parse_theme({"id": "p", "name": "P",
                                 "palette": {"dark": full_palette(primary="#0000ff")}})
        self.assertEqual(t2.tokens["dark"]["button-primary-gradient-start"], "#0000ff")

    def test_explicit_tokens_override_and_can_reference_roles(self):
        t = engine.parse_theme({"id": "p", "name": "P", "palette": {"dark": full_palette()},
                                "tokens": {"dark": {"canvas": "#abcdef", "border-focus": "$fg@0.5"}}})
        self.assertEqual(t.tokens["dark"]["canvas"], "#abcdef")
        self.assertEqual(t.tokens["dark"]["border-focus"], "rgba(238, 238, 238, 0.5)")

    def test_palette_errors(self):
        pal = full_palette()
        del pal["accent"]
        bad = [
            {"id": "p", "name": "P", "palette": {"dark": pal}},
            {"id": "p", "name": "P", "palette": {"dark": full_palette(bg="red")}},
            {"id": "p", "name": "P", "palette": {"dark": full_palette(bg="rgba(1,2,3,.5)")}},
            {"id": "p", "name": "P", "palette": {"dusk": full_palette()}},
            {"id": "p", "name": "P", "palette": {"dark": full_palette()},
             "tokens": {"dark": {"canvas": "$nope"}}},
            {"id": "p", "name": "P", "palette": {"dark": full_palette()},
             "tokens": {"dark": {"canvas": "$fg@2"}}},
            {"id": "p", "name": "P"},
        ]
        for data in bad:
            with self.assertRaises(engine.ThemeError, msg=str(data)):
                engine.parse_theme(data)

    def test_all_shipped_themes_cover_the_role_map(self):
        themes, errors = engine.load_themes()
        self.assertEqual(errors, {})
        self.assertGreaterEqual(set(themes), {"flame", "catppuccin", "catppuccin-macchiato",
                                              "catppuccin-frappe", "gruvbox"})
        for t in themes.values():
            self.assertEqual(set(t.tokens), {"light", "dark"}, t.id)
            self.assertEqual(set(t.tokens["light"]), set(t.tokens["dark"]), t.id)

    def test_catppuccin_mocha_matches_the_official_palette(self):
        t = engine.load_themes()[0]["catppuccin"]
        d = t.tokens["dark"]
        self.assertEqual((d["canvas"], d["fg"], d["state-learn"], d["state-review"]),
                         ("#1e1e2e", "#cdd6f4", "#f38ba8", "#a6e3a1"))


class CssTests(unittest.TestCase):
    def setUp(self):
        self.theme = engine.parse_theme(minimal(extra_css="a{color:red}"))

    def test_selectors_beat_anki_specificity(self):
        css = engine.build_css(self.theme)
        self.assertIn("html:root{--canvas:#fff}", css)
        self.assertIn("html:root.night-mode{--canvas:#000}", css)
        self.assertTrue(css.rstrip().endswith("a{color:red}"))

    def test_style_tag_and_js(self):
        self.assertTrue(engine.style_tag(self.theme).startswith('<style id="anki-themes">'))
        js = engine.inject_js(self.theme)
        self.assertIn("getElementById('anki-themes')", js)
        self.assertIn(json.dumps(engine.build_css(self.theme)), js)
        self.assertIn("remove()", engine.remove_js())

    def test_single_mode_theme(self):
        t = engine.parse_theme(minimal(tokens={"dark": {"canvas": "#000"}}))
        css = engine.build_css(t)
        self.assertIn("night-mode", css)
        self.assertNotIn("html:root{", css)


class QtColorsTests(unittest.TestCase):
    def test_token_to_const(self):
        self.assertEqual(engine.token_to_const("canvas-elevated"), "CANVAS_ELEVATED")

    def test_apply_restore_roundtrip(self):
        m = fake_colors()
        q = engine.QtColors(m)
        theme = engine.parse_theme(minimal(tokens={
            "light": {"canvas": "#111111"}, "dark": {"canvas": "#222222", "nope": "#333333"}}))
        unknown = q.apply(theme)
        self.assertEqual(unknown, ["nope"])
        self.assertEqual((m.CANVAS["light"], m.CANVAS["dark"]), ("#111111", "#222222"))
        self.assertEqual(m.CANVAS["comment"], "x")
        q.apply(None)
        self.assertEqual((m.CANVAS["light"], m.CANVAS["dark"]), ("#f5f5f5", "#2c2c2c"))

    def test_switching_themes_keeps_true_originals(self):
        m = fake_colors()
        q = engine.QtColors(m)
        a = engine.parse_theme(minimal(id="a", tokens={"light": {"canvas": "#aaaaaa"}}))
        b = engine.parse_theme(minimal(id="b", tokens={"light": {"fg-subtle": "#bbbbbb"}}))
        q.apply(a)
        q.apply(b)  # canvas must go back to the original, not stay "a"
        self.assertEqual(m.CANVAS["light"], "#f5f5f5")
        self.assertEqual(m.FG_SUBTLE["light"], "#bbbbbb")
        q.apply(None)
        self.assertEqual(m.FG_SUBTLE["light"], "#737373")


if __name__ == "__main__":
    unittest.main()
