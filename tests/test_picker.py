"""Renders the picker with real PyQt6 (offscreen). Skipped when PyQt6 is not installed."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

ADDON = Path(__file__).resolve().parent.parent / "addon"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    QtWidgets = None


@unittest.skipIf(QtWidgets is None, "PyQt6 not available")
class PickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        qt = types.ModuleType("aqt.qt")
        for mod in (QtCore, QtGui, QtWidgets):
            for name in dir(mod):
                setattr(qt, name, getattr(mod, name))
        aqt = types.ModuleType("aqt")
        aqt.qt = qt
        sys.modules["aqt"], sys.modules["aqt.qt"] = aqt, qt
        spec = importlib.util.spec_from_file_location(
            "anki_themes", ADDON / "__init__.py", submodule_search_locations=[str(ADDON)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules["anki_themes"] = pkg  # package shell only; __init__ is not executed
        cls.picker = importlib.import_module("anki_themes.picker")
        cls.engine = importlib.import_module("anki_themes.engine")
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @classmethod
    def tearDownClass(cls):
        for name in ("aqt", "aqt.qt", "anki_themes", "anki_themes.picker", "anki_themes.engine"):
            sys.modules.pop(name, None)

    def themes(self):
        return self.engine.load_themes(ADDON / "themes")[0]

    def test_to_qcolor(self):
        c = self.picker.to_qcolor("rgba(255, 136, 0, 0.25)")
        self.assertEqual((c.red(), c.green(), c.blue()), (255, 136, 0))
        self.assertAlmostEqual(c.alphaF(), 0.25, places=2)
        self.assertEqual(self.picker.to_qcolor("#1e1e2e").name(), "#1e1e2e")
        self.assertTrue(self.picker.to_qcolor("rgb(25.1%, 25%, 25%)").isValid())

    def test_dialog_lists_themes_and_applies_selection(self):
        applied = []
        dlg = self.picker.ThemePicker(None, self.themes(), "flame", True, applied.append)
        ids = [dlg.list.item(i).data(QtCore.Qt.ItemDataRole.UserRole) for i in range(dlg.list.count())]
        self.assertEqual(ids[0], "")
        self.assertIn("gruvbox", ids)
        self.assertEqual(dlg.selected_id(), "flame")
        self.assertFalse(dlg.apply_btn.isEnabled())  # already active
        dlg.list.setCurrentRow(ids.index("gruvbox"))
        self.assertEqual(dlg.title.text(), "Gruvbox")
        self.assertTrue(dlg.apply_btn.isEnabled())
        dlg._apply()
        self.assertEqual(applied, ["gruvbox"])

    def test_selecting_default_offers_to_turn_off(self):
        applied = []
        dlg = self.picker.ThemePicker(None, self.themes(), "flame", False, applied.append)
        dlg.list.setCurrentRow(0)
        self.assertEqual(dlg.title.text(), "Padrão do Anki")
        dlg._apply()
        self.assertEqual(applied, [""])

    def test_screenshot_when_requested(self):
        out = os.environ.get("PICKER_SHOT")
        if not out:
            self.skipTest("set PICKER_SHOT=<file.png> to save a screenshot")
        dlg = self.picker.ThemePicker(None, self.themes(), "flame", True, lambda _t: None)
        dlg.list.setCurrentRow(2)
        dlg.show()
        self.app.processEvents()
        self.assertTrue(dlg.grab().save(out))


if __name__ == "__main__":
    unittest.main()
