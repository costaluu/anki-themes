"""Theme picker dialog: a list of themes with a live mini-preview in light and dark.

Only the picker's own preview cards use the theme being browsed; the rest of
the application changes when the user presses "Aplicar".
"""
from __future__ import annotations

from typing import Callable

from aqt.qt import (
    QColor,
    QDialog,
    QFont,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLinearGradient,
    QListWidget,
    QListWidgetItem,
    QPainter,
    QPen,
    QPixmap,
    QPushButton,
    QRectF,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)

from .engine import Theme

NO_THEME = ""  # id used for "Anki default"
# Fallbacks used to draw the "Padrão do Anki" entry (Anki's own default colors).
_DEFAULT_TOKENS = {
    "light": {"canvas": "#f5f5f5", "canvas-elevated": "#ffffff", "canvas-inset": "#ffffff",
              "fg": "#020202", "fg-subtle": "#737373", "fg-link": "#1d4ed8", "border": "#c4c4c4",
              "button-bg": "#fcfcfc", "button-primary-gradient-start": "#3b82f6",
              "button-primary-gradient-end": "#306bec", "selected-bg": "rgba(214, 214, 214, 0.5)",
              "state-new": "#3b82f6", "state-learn": "#dc2626", "state-review": "#16a34a",
              "accent-card": "#60a5fa"},
    "dark": {"canvas": "#2c2c2c", "canvas-elevated": "#363636", "canvas-inset": "#2c2c2c",
             "fg": "#fcfcfc", "fg-subtle": "#858585", "fg-link": "#bfdbfe", "border": "#202020",
             "button-bg": "#404040", "button-primary-gradient-start": "#2f67e1",
             "button-primary-gradient-end": "#2652d0", "selected-bg": "rgba(147, 197, 253, 0.5)",
             "state-new": "#93c5fd", "state-learn": "#f87171", "state-review": "#22c55e",
             "accent-card": "#93c5fd"},
}


def to_qcolor(value: str) -> QColor:
    """Parse '#hex', named colors and 'rgba(r, g, b, a)' (a in 0..1) into a QColor."""
    value = value.strip()
    if value.startswith("rgb"):
        inner = value[value.index("(") + 1:value.rindex(")")]
        parts = [p.strip() for p in inner.replace("/", ",").split(",")]
        nums = []
        for p in parts[:3]:
            nums.append(round(float(p[:-1]) * 2.55) if p.endswith("%") else round(float(p)))
        alpha = float(parts[3]) if len(parts) > 3 else 1.0
        color = QColor(*nums)
        color.setAlphaF(alpha)
        return color
    return QColor(value)


class PreviewCard(QWidget):
    """A tiny painted mock of Anki (deck list + buttons) using a theme's tokens."""

    def __init__(self, title: str, tokens: dict[str, str] | None, current: bool, parent=None):
        super().__init__(parent)
        self._title = title
        self._tokens = tokens
        self._current = current
        self.setMinimumSize(250, 230)

    def set_tokens(self, tokens: dict[str, str] | None) -> None:
        self._tokens = tokens
        self.update()

    def _c(self, name: str, fallback: str = "#888888") -> QColor:
        value = (self._tokens or {}).get(name, fallback)
        return to_qcolor(value)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if not self._tokens:
            p.fillRect(0, 0, w, h, QColor("#bbbbbb"))
            p.setPen(QColor("#444444"))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       f"{self._title}\n(sem variante)")
            p.end()
            return
        p.fillRect(0, 0, w, h, self._c("canvas"))
        font = QFont(self.font())
        font.setPointSize(9)
        p.setFont(font)

        # header
        p.setPen(self._c("fg-subtle"))
        p.drawText(QRectF(12, 8, w - 24, 18), Qt.AlignmentFlag.AlignVCenter, self._title.upper())

        # card with deck rows
        card = QRectF(12, 30, w - 24, 104)
        p.setBrush(self._c("canvas-elevated"))
        p.setPen(QPen(self._c("border"), 1))
        p.drawRoundedRect(card, 8, 8)
        rows = [("Medicina", "12", "8", "64", False), ("Inglês", "5", "3", "40", True),
                ("Redes 5G", "0", "1", "22", False)]
        for i, (name, n, l, r, selected) in enumerate(rows):
            y = card.top() + 8 + i * 30
            if selected:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._c("selected-bg"))
                p.drawRoundedRect(QRectF(card.left() + 5, y, card.width() - 10, 26), 5, 5)
            p.setPen(self._c("fg"))
            p.drawText(QRectF(card.left() + 12, y, 80, 26), Qt.AlignmentFlag.AlignVCenter, name)
            # three count columns, right-aligned from the card's right edge
            for j, (val, tok) in enumerate(((n, "state-new"), (l, "state-learn"), (r, "state-review"))):
                p.setPen(self._c(tok))
                right = card.right() - 10 - (2 - j) * 34
                p.drawText(QRectF(right - 30, y, 30, 26),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, val)

        # buttons
        y = card.bottom() + 14
        btn = QRectF(12, y, 96, 30)
        grad = QLinearGradient(btn.topLeft(), btn.bottomLeft())
        grad.setColorAt(0, self._c("button-primary-gradient-start"))
        grad.setColorAt(1, self._c("button-primary-gradient-end"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(btn, 6, 6)
        p.setPen(QColor("white"))
        p.drawText(btn, Qt.AlignmentFlag.AlignCenter, "Estudar")
        btn2 = QRectF(116, y, 96, 30)
        p.setBrush(self._c("button-bg"))
        p.setPen(QPen(self._c("border"), 1))
        p.drawRoundedRect(btn2, 6, 6)
        p.setPen(self._c("fg"))
        p.drawText(btn2, Qt.AlignmentFlag.AlignCenter, "Opções")

        # link + accent bar
        p.setPen(self._c("fg-link"))
        f2 = QFont(font)
        f2.setUnderline(True)
        p.setFont(f2)
        p.drawText(QRectF(12, y + 38, 140, 18), Qt.AlignmentFlag.AlignVCenter, "link de exemplo")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._c("accent-card"))
        p.drawRoundedRect(QRectF(12, h - 10, w - 24, 4), 2, 2)

        if self._current:  # mode Anki is using right now
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(self._c("accent-card"), 2))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 4, 4)
        p.end()


def swatch_icon(light: dict[str, str] | None, dark: dict[str, str] | None) -> QIcon:
    """Round pill: left half = light variant, right half = dark variant (+ accent dot)."""
    size = 28
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for half, tokens in ((0, light), (1, dark)):
        t = tokens or dark or light or {}
        p.setClipRect(QRectF(half * size / 2, 0, size / 2, size))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(to_qcolor(t.get("canvas", "#888888")))
        p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
        p.setBrush(to_qcolor(t.get("accent-card", t.get("fg", "#444444"))))
        p.drawEllipse(QRectF(size * 0.28 + half * size * 0.22, size * 0.34, size * 0.22, size * 0.32))
    p.setClipping(False)
    p.setPen(QPen(QColor(128, 128, 128, 160), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()
    return QIcon(pm)


class ThemePicker(QDialog):
    def __init__(self, parent, themes: dict[str, Theme], active_id: str,
                 night_mode: bool, on_apply: Callable[[str], None]):
        super().__init__(parent)
        self.setWindowTitle("Temas")
        self.resize(780, 440)
        self._themes = themes
        self._active = active_id
        self._on_apply = on_apply

        self.list = QListWidget()
        self.list.setIconSize(QSize(28, 28))
        self.list.setMinimumWidth(230)
        self.list.setUniformItemSizes(True)
        entries = [(NO_THEME, "Padrão do Anki", _DEFAULT_TOKENS["light"], _DEFAULT_TOKENS["dark"])]
        for t in sorted(themes.values(), key=lambda t: t.name.casefold()):
            entries.append((t.id, t.name, t.tokens.get("light"), t.tokens.get("dark")))
        selected_row = 0
        for row, (tid, name, light, dark) in enumerate(entries):
            label = name + ("  ·  ativo" if tid == active_id else "")
            item = QListWidgetItem(swatch_icon(light, dark), label)
            item.setData(Qt.ItemDataRole.UserRole, tid)
            self.list.addItem(item)
            if tid == active_id:
                selected_row = row

        self.title = QLabel()
        title_font = QFont(self.font())
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        self.title.setFont(title_font)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setMinimumHeight(52)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.card_light = PreviewCard("Claro", None, not night_mode)
        self.card_dark = PreviewCard("Escuro", None, night_mode)
        cards = QHBoxLayout()
        cards.addWidget(self.card_light)
        cards.addWidget(self.card_dark)

        self.hint = QLabel("O Anki escolhe claro ou escuro em Ferramentas → Preferências → Aparência. "
                           "O contorno destaca o modo em uso agora.")
        self.hint.setWordWrap(True)

        self.apply_btn = QPushButton("Aplicar")
        self.apply_btn.setDefault(True)
        close_btn = QPushButton("Fechar")
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        buttons.addWidget(self.apply_btn)

        right = QVBoxLayout()
        right.addWidget(self.title)
        right.addWidget(self.desc)
        right.addLayout(cards, 1)
        right.addWidget(self.hint)
        right.addLayout(buttons)
        root = QHBoxLayout(self)
        root.addWidget(self.list)
        root.addLayout(right, 1)

        self.list.currentItemChanged.connect(lambda cur, _prev: self._show(cur))
        self.list.itemDoubleClicked.connect(lambda _item: self._apply())
        self.apply_btn.clicked.connect(self._apply)
        close_btn.clicked.connect(self.reject)
        self.list.setCurrentRow(selected_row)

    def selected_id(self) -> str:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else NO_THEME

    def _show(self, item) -> None:
        tid = item.data(Qt.ItemDataRole.UserRole) if item else NO_THEME
        if tid in self._themes:
            theme = self._themes[tid]
            self.title.setText(theme.name)
            self.desc.setText(theme.description or "")
            self.card_light.set_tokens(theme.tokens.get("light"))
            self.card_dark.set_tokens(theme.tokens.get("dark"))
        else:
            self.title.setText("Padrão do Anki")
            self.desc.setText("Desliga a extensão: o Anki volta às cores originais dele.")
            self.card_light.set_tokens(_DEFAULT_TOKENS["light"])
            self.card_dark.set_tokens(_DEFAULT_TOKENS["dark"])
        self.apply_btn.setEnabled(tid != self._active)
        self.apply_btn.setText("Já está ativo" if tid == self._active else "Aplicar")

    def _apply(self) -> None:
        tid = self.selected_id()
        if tid == self._active:
            return
        self._on_apply(tid)
        self.accept()
