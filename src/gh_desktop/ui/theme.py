"""GitGet dark-purple theme.

QPalette covers the structural Qt widget colors; QSS layers on top for
finer-grained control (tab bars, scrollbars, hover states, etc.).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

APP_NAME = "GitGet"
APP_TAGLINE = "by Obsidian Watch Group"

# Dark purple palette
BG = "#16101e"
SURFACE = "#1f1828"
SURFACE_ALT = "#251a30"
SURFACE_HI = "#2f2240"
BORDER = "#3d2d52"
TEXT = "#e8e1f5"
TEXT_MUTED = "#a094b8"
ACCENT = "#9d4edd"
ACCENT_HI = "#b56aff"
ACCENT_DARK = "#6a3d99"
SUCCESS = "#7fb069"
ERROR = "#e76f7a"
WARNING = "#f7b267"


def _qc(hex_str: str) -> QColor:
    return QColor(hex_str)


def apply_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, _qc(BG))
    pal.setColor(QPalette.ColorRole.WindowText, _qc(TEXT))
    pal.setColor(QPalette.ColorRole.Base, _qc(SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase, _qc(SURFACE_ALT))
    pal.setColor(QPalette.ColorRole.Text, _qc(TEXT))
    pal.setColor(QPalette.ColorRole.Button, _qc(SURFACE_HI))
    pal.setColor(QPalette.ColorRole.ButtonText, _qc(TEXT))
    pal.setColor(QPalette.ColorRole.BrightText, _qc("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight, _qc(ACCENT_DARK))
    pal.setColor(QPalette.ColorRole.HighlightedText, _qc("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link, _qc(ACCENT_HI))
    pal.setColor(QPalette.ColorRole.LinkVisited, _qc(ACCENT))
    pal.setColor(QPalette.ColorRole.ToolTipBase, _qc(SURFACE_ALT))
    pal.setColor(QPalette.ColorRole.ToolTipText, _qc(TEXT))
    pal.setColor(QPalette.ColorRole.PlaceholderText, _qc(TEXT_MUTED))
    pal.setColor(QPalette.ColorRole.Mid, _qc(BORDER))

    # Disabled states
    for group in (QPalette.ColorGroup.Disabled,):
        pal.setColor(group, QPalette.ColorRole.WindowText, _qc("#54487a"))
        pal.setColor(group, QPalette.ColorRole.Text, _qc("#54487a"))
        pal.setColor(group, QPalette.ColorRole.ButtonText, _qc("#54487a"))

    app.setPalette(pal)


STYLESHEET = f"""
* {{
    selection-background-color: {ACCENT_DARK};
    selection-color: #ffffff;
}}

QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
}}

QMenuBar {{
    background-color: #1a1424;
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    background: transparent;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {SURFACE_HI};
}}

QMenu {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px 6px 24px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {ACCENT_DARK};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 6px;
}}

QStatusBar {{
    background-color: #1a1424;
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {SURFACE_ALT};
    color: {TEXT_MUTED};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background-color: {SURFACE_HI};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background-color: {SURFACE_HI};
    color: {TEXT};
}}

QPushButton {{
    background-color: {SURFACE_HI};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 14px;
    border-radius: 4px;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {ACCENT_DARK};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {SURFACE};
}}
QPushButton:disabled {{
    color: #54487a;
    background-color: #221530;
    border-color: #2a1f3a;
}}
QPushButton:flat {{
    background: transparent;
    border: none;
}}
QPushButton:flat:hover {{
    background-color: {SURFACE_HI};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    color: #54487a;
    background-color: #1a1424;
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DARK};
    selection-color: #ffffff;
    outline: none;
}}

QListWidget, QTreeWidget, QTableWidget {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    alternate-background-color: {SURFACE_ALT};
    outline: none;
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: 4px;
    border-bottom: 1px solid rgba(61, 45, 82, 0.4);
}}
QListWidget::item:selected,
QTreeWidget::item:selected,
QTableWidget::item:selected {{
    background-color: {ACCENT_DARK};
    color: #ffffff;
}}
QListWidget::item:hover:!selected,
QTreeWidget::item:hover:!selected,
QTableWidget::item:hover:!selected {{
    background-color: {SURFACE_HI};
}}

QHeaderView::section {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
    padding: 6px;
    border: 0;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
}}

QSplitter::handle {{
    background-color: {BG};
}}
QSplitter::handle:horizontal {{
    width: 4px;
}}
QSplitter::handle:vertical {{
    height: 4px;
}}
QSplitter::handle:hover {{
    background-color: {ACCENT};
}}

QDockWidget {{
    color: {TEXT};
}}
QDockWidget::title {{
    background-color: {SURFACE_ALT};
    padding: 4px 8px;
    border-bottom: 1px solid {BORDER};
}}

QScrollBar:vertical {{
    background-color: #1a1424;
    width: 11px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER};
    border-radius: 5px;
    min-height: 24px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: #1a1424;
    height: 11px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {BORDER};
    border-radius: 5px;
    min-width: 24px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT_HI};
    font-weight: 600;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {SURFACE};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {ACCENT_HI};
}}

QToolTip {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
    border: 1px solid {ACCENT};
    padding: 4px;
}}

QMessageBox, QDialog {{
    background-color: {BG};
}}

QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT};
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply full GitGet theme: palette + QSS."""
    apply_palette(app)
    app.setStyleSheet(STYLESHEET)


# Convenience access from non-Qt code (banners etc.)
__all__ = [
    "ACCENT",
    "ACCENT_DARK",
    "ACCENT_HI",
    "APP_NAME",
    "APP_TAGLINE",
    "BG",
    "BORDER",
    "ERROR",
    "STYLESHEET",
    "SUCCESS",
    "SURFACE",
    "SURFACE_ALT",
    "SURFACE_HI",
    "TEXT",
    "TEXT_MUTED",
    "WARNING",
    "apply_palette",
    "apply_theme",
]
