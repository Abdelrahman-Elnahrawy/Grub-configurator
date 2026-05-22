#!/usr/bin/env python3
"""
grub_configurator/gui.py
────────────────────────
4-tab PyQt6 GUI: Splash | Themes | Settings | Log
Theme tab has sub-tabs for every theme.txt block.
"""

import logging
import sys
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QTabWidget,
    QFrame, QScrollArea, QGridLayout, QCheckBox, QSpinBox,
    QGroupBox, QListWidget, QListWidgetItem, QTextEdit,
    QLineEdit, QSlider, QMessageBox, QProgressBar
)

import grub_configurator.backend as backend
from grub_configurator.backend import ThemeConfig

log = logging.getLogger(__name__)

# ── Palette ──────────────────────────────────────────────────────────────────
AMBER  = "#E8A020"
AMBER2 = "#FFB830"
AMBER3 = "#FFB830"
DIM    = "#C07010"
BG0    = "#0D0D0D"
BG1    = "#141414"
BG2    = "#1C1C1C"
BG3    = "#242424"
BORDER = "#2A2A2A"
TEXT   = "#D0C8B0"
TEXT2  = "#888070"
GREEN  = "#50C878"
RED    = "#E05050"
BLUE   = "#5599DD"

SS = f"""
QMainWindow, QWidget {{
    background: {BG0}; color: {TEXT};
    font-family: "JetBrains Mono","Fira Mono","Courier New",monospace;
    font-size: 13px;
}}
QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG1}; }}
QTabBar::tab {{
    background: {BG2}; color: {TEXT2}; border: 1px solid {BORDER};
    padding: 10px 24px; font-size: 13px; letter-spacing: 1px;
}}
QTabBar::tab:selected {{ background: {BG1}; color: {AMBER}; border-bottom: 2px solid {AMBER}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QPushButton {{
    background: {BG2}; color: {AMBER}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 7px 16px;
    font-family: "JetBrains Mono","Fira Mono",monospace;
    font-size: 12px; letter-spacing: 1px;
}}
QPushButton:hover {{ background: {BG3}; border-color: {AMBER}; }}
QPushButton:pressed {{ background: {BG1}; color: {DIM}; }}
QPushButton#primary {{ background: {AMBER}; color: {BG0}; border: none; font-weight: bold; border-radius: 4px; padding: 7px 16px; }}
QPushButton#primary:hover {{ background: {AMBER2}; color: {BG0}; }}
QPushButton#primary:pressed {{ background: {AMBER3}; color: {BG0}; }}
QPushButton#danger  {{ border-color: {RED}; color: {RED}; }}
QPushButton#preview {{ background: {BG2}; color: {BLUE}; border: 1px solid {BLUE}; }}
QPushButton#preview:hover {{ background: {BG3}; }}
QLabel#heading  {{ font-size: 20px; font-weight: bold; color: {AMBER}; letter-spacing: 2px; }}
QLabel#sub      {{ font-size: 11px; color: {TEXT2}; letter-spacing: 1px; }}
QLabel#badge    {{
    background: {BG3}; color: {AMBER}; border: 1px solid {AMBER};
    border-radius: 3px; padding: 2px 8px; font-size: 11px;
}}
QLabel#pathbox  {{
    background: {BG2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 5px 10px; font-size: 12px;
}}
QLineEdit {{
    background: {BG2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 5px 10px;
}}
QComboBox {{
    background: {BG2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 5px 10px; min-width: 160px;
}}
QComboBox QAbstractItemView {{
    background: {BG2}; color: {TEXT}; border: 1px solid {BORDER};
    selection-background-color: {BG3}; selection-color: {AMBER};
}}
QComboBox::drop-down {{
    background: {BG3}; border: none; width: 24px;
}}
QComboBox::drop-down:hover {{ background: {AMBER3}; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT2};
    width: 0; height: 0;
}}
QComboBox::down-arrow:hover {{ border-top-color: {AMBER}; }}
QListWidget {{
    background: {BG1}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; outline: none;
}}
QListWidget::item {{ padding: 7px 12px; border-bottom: 1px solid {BORDER}; }}
QListWidget::item:selected {{ background: {BG3}; color: {AMBER}; }}
QListWidget::item:hover {{ background: {BG2}; }}
QScrollBar:vertical {{
    background: {BG1}; width: 7px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {BG3}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {AMBER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid {BORDER};
    background: {BG2}; border-radius: 3px;
}}
QCheckBox::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}
QSpinBox {{
    background: {BG2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 5px 10px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {BG3}; border: none; width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {AMBER3};
}}
QSpinBox::up-arrow {{
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT2};
    width: 0; height: 0;
}}
QSpinBox::down-arrow {{
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT2};
    width: 0; height: 0;
}}
QSpinBox::up-arrow:hover {{ border-bottom-color: {AMBER}; }}
QSpinBox::down-arrow:hover {{ border-top-color: {AMBER}; }}
QTextEdit {{
    background: {BG1}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px;
    font-family: "JetBrains Mono","Fira Mono",monospace; font-size: 12px;
}}
QGroupBox {{
    color: {AMBER}; border: 1px solid {BORDER}; border-radius: 6px;
    margin-top: 14px; padding-top: 14px;
    font-size: 12px; letter-spacing: 1px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
QSlider::groove:horizontal {{
    height: 4px; background: {BG3}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {AMBER}; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {AMBER}; border-radius: 2px; }}
QProgressBar {{
    background: {BG2}; border: 1px solid {BORDER}; border-radius: 4px;
    text-align: center; color: {TEXT}; font-size: 11px;
}}
QProgressBar::chunk {{ background: {AMBER}; border-radius: 3px; }}
"""

# ── Worker ───────────────────────────────────────────────────────────────────
class Sig(QObject):
    done = pyqtSignal(bool, str)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = Sig()

    def run(self):
        try:
            r = self.fn(*self.args, **self.kwargs)
            ok, msg = (r if isinstance(r, tuple) and len(r) == 2 else (True, str(r)))
            self.signals.done.emit(bool(ok), str(msg))
        except Exception as e:
            self.signals.done.emit(False, str(e))

# ── Helpers ──────────────────────────────────────────────────────────────────
def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {BORDER};")
    return f

def _label(text: str, obj: str = "") -> QLabel:
    lbl = QLabel(text)
    if obj:
        lbl.setObjectName(obj)
    return lbl

# ── Image preview widget ─────────────────────────────────────────────────────
class ImagePreview(QLabel):
    def __init__(self, placeholder="No image selected", w=320, h=180, parent=None):
        super().__init__(parent)
        self._pix = None
        self.placeholder = placeholder
        self.setMinimumSize(w, h)
        self.setMaximumHeight(h+60)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"background:{BG2};border:1px dashed {BORDER};border-radius:6px;color:{TEXT2};font-size:12px;")
        self.setText(placeholder)

    def set_image(self, path: Path):
        pix = QPixmap(str(path))
        if pix.isNull():
            self.clear()
            return
        self._pix = pix
        self._refresh()

    def set_image_pixmap(self, pix: QPixmap):
        self._pix = pix
        self._refresh()

    def clear(self):
        self._pix = None
        self.setPixmap(QPixmap())
        self.setText(self.placeholder)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pix:
            self._refresh()

    def _refresh(self):
        if self._pix:
            scaled = self._pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
            self.setText("")

# ── Toast ────────────────────────────────────────────────────────────────────
class Toast(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.timeout.connect(self.hide)
        self.hide()

    def show_msg(self, msg: str, ok: bool = True, ms: int = 6000):
        color = GREEN if ok else RED
        self.setStyleSheet(f"background:{BG2};color:{color};border:1px solid {color};border-radius:4px;padding:8px 16px;font-size:12px;")
        self.setText(("✓" if ok else "✗") + "  " + msg)
        self.show()
        self._t.start(ms)

# ── Color picker button ─────────────────────────────────────────────────────
class ColorBtn(QPushButton):
    def __init__(self, color: str = "#ffffff", parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 28)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: str):
        self._color = color
        self.setStyleSheet(f"background:{color};border:1px solid {BORDER};border-radius:3px;")

    def get_color(self) -> str:
        return self._color

    def _pick(self):
        from PyQt6.QtWidgets import QColorDialog
        dlg = QColorDialog(QColor(self._color), self)
        dlg.setWindowTitle("Pick color")
        dlg.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dlg.setStyleSheet(f"""
            QWidget {{ background: {BG1}; color: {TEXT}; }}
            QLineEdit {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; }}
            QPushButton {{ background: {BG2}; color: {AMBER}; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 12px; }}
            QPushButton:hover {{ background: {BG3}; border-color: {AMBER}; }}
            QLabel {{ color: {TEXT}; }}
            QSpinBox {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; }}
        """)
        if dlg.exec():
            self.set_color(dlg.currentColor().name())

# ── Font picker row ─────────────────────────────────────────────────────────
class FontRow(QWidget):
    def __init__(self, current_font: str = "unicode", current_size: int = 20,
                 status_cb=None, parent=None):
        super().__init__(parent)
        self._status = status_cb
        self._fonts = backend.list_system_fonts()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(6)

        self.combo = QComboBox()
        self.combo.addItem("unicode (default)")
        for name, _ in self._fonts:
            self.combo.addItem(name)
        self._set_font_text(current_font)
        lay.addWidget(self.combo, 1)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 72)
        self.size_spin.setValue(current_size)
        self.size_spin.setFixedWidth(64)
        lay.addWidget(self.size_spin)

        btn = QPushButton("⚙ Build .pf2")
        btn.setToolTip("Convert selected TTF → .pf2 and save to theme/fonts/")
        btn.clicked.connect(self._build)
        lay.addWidget(btn)

    def _set_font_text(self, font: str):
        idx = 0
        for i in range(self.combo.count()):
            if self.combo.itemText(i).lower().startswith(font.lower().split()[0]):
                idx = i
                break
        self.combo.setCurrentIndex(idx)

    def _build(self):
        idx = self.combo.currentIndex()
        if idx == 0:
            if self._status:
                self._status("'unicode' is built‑in – no .pf2 needed", True)
            return
        _, ttf_path = self._fonts[idx-1]
        name = self.combo.currentText()
        size = self.size_spin.value()
        w = Worker(backend.build_pf2_font, ttf_path, size, name)
        w.signals.done.connect(lambda ok, msg: (
            self._status(msg, ok) if self._status else None
        ))
        QThreadPool.globalInstance().start(w)
        if self._status:
            self._status(f"Building {name} {size}pt…", True)

    def get_font_string(self) -> str:
        idx = self.combo.currentIndex()
        if idx == 0:
            return "unicode"
        name = self.combo.currentText()
        size = self.size_spin.value()
        return f"{name} {size}"

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SPLASH SCREEN
# ══════════════════════════════════════════════════════════════════════════════
class SplashTab(QWidget):
    def __init__(self, status_cb, state: dict, parent=None):
        super().__init__(parent)
        self.status = status_cb
        self.state = state
        self.themes = [
            t for t in backend.list_plymouth_themes()
            if backend.get_plymouth_theme_frames(t)[0]
        ]
        self.active = backend.get_active_plymouth_theme()
        self.favorites = [t for t in self.state.get("splash_favorites", []) if t in self.themes]
        self._anim_timer = None
        self._anim_frames = []
        self._anim_idx = 0
        self._anim_shown = 0
        self._anim_total = 0
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24,20,24,20)
        root.addWidget(_label("SPLASH SCREEN", "heading"))
        root.addWidget(_label("Select a Plymouth boot splash theme.", "sub"))
        root.addWidget(_hline())

        content = QHBoxLayout()
        content.setSpacing(18)

        # Installed themes list
        left = QVBoxLayout()
        left.addWidget(_label("Installed Plymouth themes:"))
        self.lst = QListWidget()
        self.lst.setMinimumWidth(280)
        self.lst.currentItemChanged.connect(self._on_select)
        left.addWidget(self.lst, 1)

        fav_row = QHBoxLayout()
        self.fav_btn = QPushButton("☆ Add favorite")
        self.fav_btn.clicked.connect(self._toggle_favorite)
        self.fav_btn.setEnabled(False)
        fav_row.addWidget(self.fav_btn)
        fav_row.addStretch()
        left.addLayout(fav_row)

        active_row = QHBoxLayout()
        active_row.addWidget(_label("Active:"))
        self.active_lbl = _label(self.active or "unknown", "badge")
        active_row.addWidget(self.active_lbl)
        active_row.addStretch()
        left.addLayout(active_row)

        content.addLayout(left, 1)

        # Favorite themes list
        middle = QVBoxLayout()
        middle.addWidget(_label("Favorite themes:"))
        self.fav_lst = QListWidget()
        self.fav_lst.setMinimumWidth(260)
        self.fav_lst.currentItemChanged.connect(self._on_select)
        middle.addWidget(self.fav_lst, 1)
        self.fav_count_lbl = _label(f"{len(self.favorites)} favorites", "sub")
        count_row = QHBoxLayout()
        count_row.addWidget(self.fav_count_lbl)
        count_row.addStretch()
        middle.addLayout(count_row)
        content.addLayout(middle, 1)

        # Preview panel
        right = QVBoxLayout()
        right.addWidget(_label("Preview:"))
        self.preview = ImagePreview("No preview available", 180, 300)
        right.addWidget(self.preview)
        preview_opts = QHBoxLayout()
        preview_opts.addWidget(_label("Duration:"))
        self.preview_spin = QSpinBox()
        self.preview_spin.setRange(1, 15)
        self.preview_spin.setValue(5)
        self.preview_spin.setFixedWidth(64)
        preview_opts.addWidget(self.preview_spin)
        preview_opts.addStretch()
        right.addLayout(preview_opts)
        content.addLayout(right, 2)

        root.addLayout(content, 1)
        root.addWidget(_hline())

        btn_apply = QPushButton("✓  Set Plymouth Theme")
        btn_apply.setObjectName("primary")
        btn_apply.clicked.connect(self._apply)
        root.addWidget(btn_apply)

        self._refresh_theme_list()
        self._refresh_favorite_list()

    def _refresh_theme_list(self):
        self.lst.clear()
        if not self.themes:
            self.lst.addItem("(no Plymouth themes found)")
            return
        for t in self.themes:
            label = t
            if t in self.favorites:
                label = f"♥ {label}"
            if t == self.active:
                label = f"★ {label}"
            item = QListWidgetItem(label)
            item.setForeground(QColor(AMBER)) if t == self.active else None
            self.lst.addItem(item)

    def _refresh_favorite_list(self):
        self.fav_lst.clear()
        if not self.favorites:
            self.fav_lst.addItem("(no favorites yet)")
            self.fav_count_lbl.setText("0 favorites")
            return
        for t in self.favorites:
            item = QListWidgetItem(f"★ {t}")
            self.fav_lst.addItem(item)
        self.fav_count_lbl.setText(f"{len(self.favorites)} favorites")

    def _current_theme_name(self, item):
        if not item:
            return ""
        import re
        return re.sub(r'^[^A-Za-z0-9_-]+', '', item.text()).strip()

    def _update_fav_button(self, theme_name: str):
        if not theme_name:
            self.fav_btn.setEnabled(False)
            self.fav_btn.setText("☆ Add favorite")
            return
        self.fav_btn.setEnabled(True)
        if theme_name in self.favorites:
            self.fav_btn.setText("★ Remove favorite")
        else:
            self.fav_btn.setText("☆ Add favorite")

    def _on_select(self, item, previous=None):
        if not item:
            return
        name = self._current_theme_name(item)
        self._update_fav_button(name)
        self._stop_animation()
        for d in backend.SPLASH_DIRS:
            p = d / name / "preview.png"
            if p.exists():
                self.preview.set_image(p)
                break
        else:
            self.preview.clear()
        self._start_animation(name)

    def _stop_animation(self):
        if hasattr(self, "_anim_timer") and self._anim_timer:
            self._anim_timer.stop()
            self._anim_timer = None
        self._anim_frames = []
        self._anim_idx = 0
        self._anim_shown = 0
        self._anim_total = 0

    def _start_animation(self, theme_name: str):
        frames, fps = backend.get_plymouth_theme_frames(theme_name)
        if not frames:
            self.status(f"No frames found for '{theme_name}'", False)
            return

        import re as _re
        frames = sorted(
            frames,
            key=lambda p: int(_re.search(r"\d+", p.stem).group()) if _re.search(r"\d+", p.stem) else 0
        )
        self._anim_frames = [QPixmap(str(f)) for f in frames]
        self._anim_frames = [p for p in self._anim_frames if not p.isNull()]
        if not self._anim_frames:
            self.status(f"Could not load frames for '{theme_name}'", False)
            return

        duration = self.preview_spin.value()
        self._anim_idx = 0
        self._anim_shown = 0
        self._anim_total = int(fps * duration)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(int(1000 / fps))
        self._anim_timer.timeout.connect(self._next_frame)
        self._anim_timer.start()

    def _next_frame(self):
        if self._anim_shown >= self._anim_total:
            self._anim_idx = 0
            self._anim_shown = 0
        pix = self._anim_frames[self._anim_idx % len(self._anim_frames)]
        self.preview.set_image_pixmap(pix)
        self._anim_idx += 1
        self._anim_shown += 1

    def _toggle_favorite(self):
        item = self.lst.currentItem() or self.fav_lst.currentItem()
        if not item:
            self.status("Select a theme first", False)
            return
        theme = self._current_theme_name(item)
        if not theme or theme not in self.themes:
            self.status("Selected theme is unavailable", False)
            return
        if theme in self.favorites:
            self.favorites.remove(theme)
            self.status(f"Removed '{theme}' from favorites", True)
        else:
            self.favorites.append(theme)
            self.status(f"Added '{theme}' to favorites", True)
        self._refresh_theme_list()
        self._refresh_favorite_list()
        self._update_fav_button(theme)
        # Keep the system-wide state file in sync so the boot randomizer can read it.
        w = Worker(backend.sync_favorites_to_system, list(self.favorites))
        w.signals.done.connect(lambda ok, msg: (
            log.debug("sync_favorites_to_system: %s", msg)
        ))
        QThreadPool.globalInstance().start(w)

    def _apply(self):
        item = self.lst.currentItem() or self.fav_lst.currentItem()
        if not item:
            self.status("Select a theme first", False)
            return
        name = self._current_theme_name(item)
        w = Worker(backend.set_plymouth_theme, name)
        w.signals.done.connect(lambda ok, msg: self.status(msg, ok))
        QThreadPool.globalInstance().start(w)
        self.status(f"Applying Plymouth theme '{name}'…", True)

    def get_state(self) -> dict:
        return {"splash_favorites": self.favorites}

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THEMES (with sub-tabs for each section)
# ══════════════════════════════════════════════════════════════════════════════

class _ThemeSection(QWidget):
    """Base class for a sub-tab in Themes."""
    def __init__(self, cfg: ThemeConfig, status_cb, screen_res: str, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.status = status_cb
        self.screen_res = screen_res
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        self.lay = QVBoxLayout(inner)
        self.lay.setSpacing(14)
        self.lay.setContentsMargins(24,20,24,20)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self._build()
        self.lay.addStretch()

    def _build(self):
        raise NotImplementedError

    def sync_to_cfg(self):
        """Called before apply – update cfg from widgets."""
        pass

# ── Background ────────────────────────────────────────────────────────────────
class BgSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("BACKGROUND", "heading"))
        self.lay.addWidget(_label("Pick a wallpaper for the GRUB menu background.", "sub"))
        self.lay.addWidget(_hline())

        # after
        gal_group = QGroupBox("WALLPAPERS  (theme/wallpapers/)")
        gl = QHBoxLayout(gal_group)

        left = QVBoxLayout()
        self.img_list = QListWidget()
        self._refresh_list()
        self.img_list.currentItemChanged.connect(self._on_select)
        left.addWidget(self.img_list)

        btn_import = QPushButton("⊕  Import image…")
        btn_import.clicked.connect(self._import)
        left.addWidget(btn_import)

        gl.addLayout(left, 1)
        self.preview = ImagePreview("Select a wallpaper to preview", 480, 270)
        gl.addWidget(self.preview, 1)
        self.lay.addWidget(gal_group)
        
        cur_row = QHBoxLayout()
        cur_row.addWidget(_label("Active background file:"))
        self.cur_lbl = _label(self.cfg.background_file, "badge")
        cur_row.addWidget(self.cur_lbl)
        cur_row.addStretch()
        self.lay.addLayout(cur_row)

    def _refresh_list(self):
        self.img_list.clear()
        for p in backend.list_wallpapers():
            self.img_list.addItem(p.name)

    def _on_select(self, item):
        if not item: return
        name = item.text()
        path = backend.OUR_WALLPAPERS_DIR / name
        self.preview.set_image(path)
        if self.preview._pix:
            w = max(240, min(self.preview._pix.width(), 600))
            h = max(135, min(self.preview._pix.height(), 400))
            self.preview.setFixedSize(w, h)
        self.cfg.background_file = f"wallpapers/{name}"
        self.cur_lbl.setText(self.cfg.background_file)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import wallpaper", filter="Images (*.png *.jpg *.jpeg *.bmp *.tga)")
        if not path: return
        w = Worker(backend.import_wallpaper, Path(path), self.screen_res)
        w.signals.done.connect(self._on_imported)
        QThreadPool.globalInstance().start(w)

    def _on_imported(self, ok: bool, msg: str):
        self.status(msg, ok)
        if ok:
            self._refresh_list()

# ── Subtitle Section ─────────────────────────────────────────────────────────
class SubtitleSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("SUBTITLE LABEL", "heading"))
        self.lay.addWidget(_label("Text label shown below the title area.", "sub"))
        self.lay.addWidget(_hline())

        self.enabled_chk = QCheckBox("Enable subtitle label")
        self.enabled_chk.setChecked(self.cfg.subtitle_enabled)
        self.enabled_chk.toggled.connect(lambda v: setattr(self.cfg, "subtitle_enabled", v))
        self.lay.addWidget(self.enabled_chk)

        g = QGroupBox("CONTENT")
        gl = QGridLayout(g)
        gl.addWidget(_label("Text:"), 0,0)
        self.text_edit = QLineEdit(self.cfg.subtitle_text)
        gl.addWidget(self.text_edit, 0,1,1,2)

        gl.addWidget(_label("Font:"), 1,0)
        self.font_row = FontRow(self.cfg.subtitle_font, 32, self.status)
        gl.addWidget(self.font_row, 1,1,1,2)

        gl.addWidget(_label("Color:"), 2,0)
        self.color_btn = ColorBtn(self.cfg.subtitle_color)
        gl.addWidget(self.color_btn, 2,1)

        gl.addWidget(_label("Align:"), 3,0)
        self.align_combo = QComboBox()
        self.align_combo.addItems(["center", "left", "right"])
        self.align_combo.setCurrentText(self.cfg.subtitle_align)
        gl.addWidget(self.align_combo, 3,1)
        self.lay.addWidget(g)

        pg = QGroupBox("POSITION & SIZE")
        pgl = QGridLayout(pg)
        for row_i, (label, attr) in enumerate([
            ("Left:",  "subtitle_left"),
            ("Top:",   "subtitle_top"),
            ("Width:", "subtitle_width"),
        ]):
            pgl.addWidget(_label(label), row_i, 0)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 100)
            try: v = int(getattr(self.cfg, attr).rstrip("%"))
            except: v = 0
            sl.setValue(v)
            lbl = QLabel(f"{v}%"); lbl.setFixedWidth(40)
            sl.valueChanged.connect(lambda n, a=attr, lb=lbl: (setattr(self.cfg, a, f"{n}%"), lb.setText(f"{n}%")))
            pgl.addWidget(sl, row_i, 1)
            pgl.addWidget(lbl, row_i, 2)
        pgl.addWidget(_label("Height (px):"), 3,0)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(10,200)
        self.height_spin.setValue(self.cfg.subtitle_height)
        pgl.addWidget(self.height_spin, 3,1)
        self.lay.addWidget(pg)

    def sync_to_cfg(self):
        self.cfg.subtitle_text = self.text_edit.text()
        self.cfg.subtitle_font = self.font_row.get_font_string()
        self.cfg.subtitle_color = self.color_btn.get_color()
        self.cfg.subtitle_align = self.align_combo.currentText()
        self.cfg.subtitle_height = self.height_spin.value()

# ── Boot Menu Section ────────────────────────────────────────────────────────
class MenuSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("BOOT MENU", "heading"))
        self.lay.addWidget(_label("The list of OS entries. Position, fonts, colors, icons.", "sub"))
        self.lay.addWidget(_hline())

        fg = QGroupBox("FONTS")
        fgl = QGridLayout(fg)
        fgl.addWidget(_label("Item font:"), 0,0)
        self.item_font = FontRow(self.cfg.menu_item_font, 20, self.status)
        fgl.addWidget(self.item_font, 0,1)
        fgl.addWidget(_label("Selected font:"), 1,0)
        self.sel_font = FontRow(self.cfg.menu_selected_font, 32, self.status)
        fgl.addWidget(self.sel_font, 1,1)
        self.lay.addWidget(fg)

        cg = QGroupBox("COLORS")
        cgl = QGridLayout(cg)
        cgl.addWidget(_label("Item color:"), 0,0)
        self.item_color = ColorBtn(self.cfg.menu_item_color)
        cgl.addWidget(self.item_color, 0,1)
        cgl.addWidget(_label("Selected color:"), 1,0)
        self.sel_color = ColorBtn(self.cfg.menu_selected_color)
        cgl.addWidget(self.sel_color, 1,1)
        self.lay.addWidget(cg)

        icon_g = QGroupBox("ICONS")
        igl = QGridLayout(icon_g)
        igl.addWidget(_label("Selected icon:"), 0,0)
        self.sel_icon_lbl = _label(str(backend.OUR_ICONS_DIR / "selectedIcon_w.png") if (backend.OUR_ICONS_DIR / "selectedIcon_w.png").exists() else "Not set", "pathbox")
        btn_sel = QPushButton("Browse…")
        btn_sel.clicked.connect(lambda: self._import_icon("selected"))
        igl.addWidget(self.sel_icon_lbl, 0,1)
        igl.addWidget(btn_sel, 0,2)

        igl.addWidget(_label("Unselected icon:"), 1,0)
        self.unsel_icon_lbl = _label(str(backend.OUR_ICONS_DIR / "notSelectedIcon_w.png") if (backend.OUR_ICONS_DIR / "notSelectedIcon_w.png").exists() else "Not set", "pathbox")
        btn_unsel = QPushButton("Browse…")
        btn_unsel.clicked.connect(lambda: self._import_icon("notselected"))
        igl.addWidget(self.unsel_icon_lbl, 1,1)
        igl.addWidget(btn_unsel, 1,2)
        self.lay.addWidget(icon_g)

        sg = QGroupBox("SIZE & SPACING")
        sgl = QGridLayout(sg)
        specs = [
            ("Icon width:",  "menu_icon_width",  8,64),
            ("Icon height:", "menu_icon_height", 8,64),
            ("Icon space:",  "menu_icon_space",  0,40),
            ("Item height:",  "menu_item_height", 16,80),
            ("Item padding:","menu_item_padding", 0,40),
            ("Item spacing:","menu_item_spacing", 0,40),
        ]
        self._spins = {}
        for row_i, (label, attr, mn, mx) in enumerate(specs):
            sgl.addWidget(_label(label), row_i, 0)
            sp = QSpinBox()
            sp.setRange(mn, mx)
            sp.setValue(int(getattr(self.cfg, attr)))
            sgl.addWidget(sp, row_i, 1)
            self._spins[attr] = sp
        scroll_row = len(specs)
        sgl.addWidget(_label("Scrollbar:"), scroll_row, 0)
        self.scrollbar_chk = QCheckBox("Enable")
        self.scrollbar_chk.setChecked(self.cfg.menu_scrollbar)
        sgl.addWidget(self.scrollbar_chk, scroll_row, 1)
        self.lay.addWidget(sg)

        pg = QGroupBox("POSITION & SIZE")
        pgl = QGridLayout(pg)
        for row_i, (label, attr) in enumerate([
            ("Left:",  "menu_left"),
            ("Top:",   "menu_top"),
            ("Width:",  "menu_width"),
            ("Height:","menu_height"),
        ]):
            pgl.addWidget(_label(label), row_i, 0)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0,100)
            try: v = int(getattr(self.cfg, attr).rstrip("%"))
            except: v = 0
            sl.setValue(v)
            lbl = QLabel(f"{v}%"); lbl.setFixedWidth(40)
            sl.valueChanged.connect(lambda n, a=attr, lb=lbl: (setattr(self.cfg, a, f"{n}%"), lb.setText(f"{n}%")))
            pgl.addWidget(sl, row_i, 1)
            pgl.addWidget(lbl, row_i, 2)
        self.lay.addWidget(pg)

    def _import_icon(self, kind: str):
        path, _ = QFileDialog.getOpenFileName(self, f"Select {kind} icon", filter="PNG Images (*.png)")
        if not path: return
        w = Worker(backend.import_icon, Path(path), kind)
        w.signals.done.connect(lambda ok, msg: self._on_icon(ok, msg, kind))
        QThreadPool.globalInstance().start(w)

    def _on_icon(self, ok: bool, msg: str, kind: str):
        self.status(msg, ok)
        if ok:
            if kind == "selected":
                self.sel_icon_lbl.setText(str(backend.OUR_ICONS_DIR / "selectedIcon_w.png"))
            else:
                self.unsel_icon_lbl.setText(str(backend.OUR_ICONS_DIR / "notSelectedIcon_w.png"))

    def sync_to_cfg(self):
        self.cfg.menu_item_font = self.item_font.get_font_string()
        self.cfg.menu_selected_font = self.sel_font.get_font_string()
        self.cfg.menu_item_color = self.item_color.get_color()
        self.cfg.menu_selected_color = self.sel_color.get_color()
        self.cfg.menu_scrollbar = self.scrollbar_chk.isChecked()
        for attr, sp in self._spins.items():
            setattr(self.cfg, attr, sp.value())

# ── Progress Bar Section ─────────────────────────────────────────────────────
class ProgressSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("PROGRESS BAR", "heading"))
        self.lay.addWidget(_label("Timeout countdown bar.", "sub"))
        self.lay.addWidget(_hline())
        self.enabled_chk = QCheckBox("Enable progress bar")
        self.enabled_chk.setChecked(self.cfg.progress_enabled)
        self.enabled_chk.toggled.connect(lambda v: setattr(self.cfg, "progress_enabled", v))
        self.lay.addWidget(self.enabled_chk)

        g = QGroupBox("COLORS & SIZE")
        gl = QGridLayout(g)
        gl.addWidget(_label("Foreground:"), 0,0); self.fg_btn = ColorBtn(self.cfg.progress_fg_color); gl.addWidget(self.fg_btn,0,1)
        gl.addWidget(_label("Background:"), 1,0); self.bg_btn = ColorBtn(self.cfg.progress_bg_color); gl.addWidget(self.bg_btn,1,1)
        gl.addWidget(_label("Border:"), 2,0);    self.border_btn = ColorBtn(self.cfg.progress_border_color); gl.addWidget(self.border_btn,2,1)
        gl.addWidget(_label("Height (px):"), 3,0)
        self.height_spin = QSpinBox(); self.height_spin.setRange(1,100); self.height_spin.setValue(self.cfg.progress_height); gl.addWidget(self.height_spin,3,1)
        self.lay.addWidget(g)

        pg = QGroupBox("POSITION")
        pgl = QGridLayout(pg)
        for row_i, (label, attr) in enumerate([("Left:","progress_left"),("Top:","progress_top"),("Width:","progress_width")]):
            pgl.addWidget(_label(label), row_i,0)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0,100)
            try: v = int(getattr(self.cfg, attr).rstrip("%"))
            except: v = 0
            sl.setValue(v); lbl = QLabel(f"{v}%"); lbl.setFixedWidth(40)
            sl.valueChanged.connect(lambda n, a=attr, lb=lbl: (setattr(self.cfg, a, f"{n}%"), lb.setText(f"{n}%")))
            pgl.addWidget(sl, row_i,1); pgl.addWidget(lbl, row_i,2)
        self.lay.addWidget(pg)

    def sync_to_cfg(self):
        self.cfg.progress_fg_color = self.fg_btn.get_color()
        self.cfg.progress_bg_color = self.bg_btn.get_color()
        self.cfg.progress_border_color = self.border_btn.get_color()
        self.cfg.progress_height = self.height_spin.value()

# ── Countdown Section ────────────────────────────────────────────────────────
class CountdownSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("COUNTDOWN LABEL", "heading"))
        self.lay.addWidget(_label("Text showing remaining seconds.", "sub"))
        self.lay.addWidget(_hline())
        self.enabled_chk = QCheckBox("Enable countdown")
        self.enabled_chk.setChecked(self.cfg.countdown_enabled)
        self.enabled_chk.toggled.connect(lambda v: setattr(self.cfg, "countdown_enabled", v))
        self.lay.addWidget(self.enabled_chk)

        g = QGroupBox("STYLE")
        gl = QGridLayout(g)
        gl.addWidget(_label("Font:"), 0,0); self.font_row = FontRow(self.cfg.countdown_font, 18, self.status); gl.addWidget(self.font_row,0,1)
        gl.addWidget(_label("Color:"), 1,0); self.color_btn = ColorBtn(self.cfg.countdown_color); gl.addWidget(self.color_btn,1,1)
        gl.addWidget(_label("Align:"), 2,0); self.align_combo = QComboBox(); self.align_combo.addItems(["center","left","right"]); self.align_combo.setCurrentText(self.cfg.countdown_align); gl.addWidget(self.align_combo,2,1)
        self.lay.addWidget(g)

        pg = QGroupBox("POSITION")
        pgl = QGridLayout(pg)
        for row_i, (label, attr) in enumerate([("Left:","countdown_left"),("Top:","countdown_top"),("Width:","countdown_width")]):
            pgl.addWidget(_label(label), row_i,0)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0,100)
            try: v = int(getattr(self.cfg, attr).rstrip("%"))
            except: v = 0
            sl.setValue(v); lbl = QLabel(f"{v}%"); lbl.setFixedWidth(40)
            sl.valueChanged.connect(lambda n, a=attr, lb=lbl: (setattr(self.cfg, a, f"{n}%"), lb.setText(f"{n}%")))
            pgl.addWidget(sl, row_i,1); pgl.addWidget(lbl, row_i,2)
        self.lay.addWidget(pg)

    def sync_to_cfg(self):
        self.cfg.countdown_font = self.font_row.get_font_string()
        self.cfg.countdown_color = self.color_btn.get_color()
        self.cfg.countdown_align = self.align_combo.currentText()

# ── Title Image Section ──────────────────────────────────────────────────────
class TitleImageSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("TITLE IMAGE", "heading"))
        self.lay.addWidget(_label("Optional image at the top.", "sub"))
        self.lay.addWidget(_hline())
        self.enabled_chk = QCheckBox("Enable title image")
        self.enabled_chk.setChecked(self.cfg.title_image_enabled)
        self.enabled_chk.toggled.connect(lambda v: setattr(self.cfg, "title_image_enabled", v))
        self.lay.addWidget(self.enabled_chk)

        g = QGroupBox("IMAGE FILE")
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        self.path_lbl = _label(self.cfg.title_image_file or "Not set", "pathbox")
        self.path_lbl.setWordWrap(True)
        btn = QPushButton("Browse…")
        btn.clicked.connect(self._pick)
        row.addWidget(self.path_lbl, 1); row.addWidget(btn)
        gl.addLayout(row)
        self.preview = ImagePreview("No image", 400, 120)
        gl.addWidget(self.preview)
        self.lay.addWidget(g)

        pg = QGroupBox("POSITION")
        pgl = QGridLayout(pg)
        def add_pct(row_i, label, attr):
            pgl.addWidget(_label(label), row_i,0)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0,100)
            try: v = int(getattr(self.cfg, attr).rstrip("%"))
            except: v = 0
            sl.setValue(v); lbl = QLabel(f"{v}%"); lbl.setFixedWidth(40)
            sl.valueChanged.connect(lambda n, a=attr, lb=lbl: (setattr(self.cfg, a, f"{n}%"), lb.setText(f"{n}%")))
            pgl.addWidget(sl, row_i,1); pgl.addWidget(lbl, row_i,2)
        add_pct(0, "Left:", "title_image_left")
        add_pct(1, "Top:",  "title_image_top")
        self.lay.addWidget(pg)

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select title image", filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if not path: return
        src = Path(path)
        dest = backend.OUR_THEME_DIR / src.name
        w = Worker(lambda: backend._run(["cp", str(src), str(dest)]))
        w.signals.done.connect(lambda ok, _: (
            setattr(self.cfg, "title_image_file", src.name),
            self.path_lbl.setText(src.name),
            self.preview.set_image(dest)
        ) if ok else self.status("Copy failed", False))
        QThreadPool.globalInstance().start(w)

# ── Footer Image Section ─────────────────────────────────────────────────────
class FooterSection(_ThemeSection):
    def _build(self):
        self.lay.addWidget(_label("FOOTER IMAGE", "heading"))
        self.lay.addWidget(_label("Optional image at the bottom.", "sub"))
        self.lay.addWidget(_hline())
        self.enabled_chk = QCheckBox("Enable footer image")
        self.enabled_chk.setChecked(self.cfg.footer_image_enabled)
        self.enabled_chk.toggled.connect(lambda v: setattr(self.cfg, "footer_image_enabled", v))
        self.lay.addWidget(self.enabled_chk)

        g = QGroupBox("IMAGE FILE")
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        self.path_lbl = _label(self.cfg.footer_image_file or "Not set", "pathbox")
        self.path_lbl.setWordWrap(True)
        btn = QPushButton("Browse…")
        btn.clicked.connect(self._pick)
        row.addWidget(self.path_lbl,1); row.addWidget(btn)
        gl.addLayout(row)
        self.preview = ImagePreview("No image", 400, 120)
        gl.addWidget(self.preview)
        self.lay.addWidget(g)

        pg = QGroupBox("POSITION")
        pgl = QGridLayout(pg)
        def add_pct(row_i, label, attr):
            pgl.addWidget(_label(label), row_i,0)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0,100)
            try: v = int(getattr(self.cfg, attr).rstrip("%"))
            except: v = 0
            sl.setValue(v); lbl = QLabel(f"{v}%"); lbl.setFixedWidth(40)
            sl.valueChanged.connect(lambda n, a=attr, lb=lbl: (setattr(self.cfg, a, f"{n}%"), lb.setText(f"{n}%")))
            pgl.addWidget(sl, row_i,1); pgl.addWidget(lbl, row_i,2)
        add_pct(0, "Left:", "footer_image_left")
        add_pct(1, "Top:",  "footer_image_top")
        self.lay.addWidget(pg)

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select footer image", filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if not path: return
        src = Path(path)
        dest = backend.OUR_THEME_DIR / src.name
        import shutil
        try:
            shutil.copy2(src, dest)
            self.cfg.footer_image_file = src.name
            self.path_lbl.setText(src.name)
            self.preview.set_image(dest)
        except Exception as e:
            self.status(str(e), False)

# ── ThemesTab (sub-tabs container) ───────────────────────────────────────────
class ThemesTab(QWidget):
    def __init__(self, cfg: ThemeConfig, status_cb, screen_res: str, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.status = status_cb
        self.screen_res = screen_res
        self._sections = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        self.sub_tabs = QTabWidget()
        # order as desired
        section_defs = [
            ("🖼 Background",   BgSection),
            ("💬 Subtitle",    SubtitleSection),
            ("📋 Boot Menu",   MenuSection),
            ("⏳ Progress Bar",ProgressSection),
            ("🕐 Countdown",   CountdownSection),
            ("🏷 Title Image",  TitleImageSection),
            ("🔻 Footer",      FooterSection),
        ]
        for name, cls in section_defs:
            sec = cls(self.cfg, self.status, self.screen_res)
            self._sections.append(sec)
            self.sub_tabs.addTab(sec, name)

        root.addWidget(self.sub_tabs, 1)

    def sync_all(self):
        for sec in self._sections:
            sec.sync_to_cfg()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
class SettingsTab(QWidget):
    def __init__(self, status_cb, screen_res: str, state: dict, parent=None):
        super().__init__(parent)
        self.status = status_cb
        self.screen_res = screen_res
        self.randomizer_enabled = backend.is_splash_randomizer_enabled()
        self._build(state)

    def _build(self, state: dict):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24,20,24,20)

        root.addWidget(_label("SETTINGS", "heading"))
        root.addWidget(_label("GRUB boot settings written to /etc/default/grub.", "sub"))
        root.addWidget(_hline())

        g = QGroupBox("BOOT OPTIONS")
        gl = QGridLayout(g)
        gl.addWidget(_label("Timeout (seconds):"), 0,0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0,60)
        self.timeout_spin.setValue(state.get("timeout", backend.get_grub_timeout()))
        gl.addWidget(self.timeout_spin, 0,1)

        gl.addWidget(_label("Screen resolution:"), 1,0)
        self.res_combo = QComboBox()
        options = ["auto", self.screen_res, "1920x1080", "2560x1440", "3840x2160", "1366x768", "1280x720", "1024x768"]
        seen = set()
        for r in options:
            if r not in seen:
                seen.add(r)
                self.res_combo.addItem(r)
        saved_res = state.get("resolution", backend.get_grub_resolution())
        idx = self.res_combo.findText(saved_res)
        self.res_combo.setCurrentIndex(max(idx,0))
        gl.addWidget(self.res_combo, 1,1)

        btn_detect = QPushButton("⟳ Re-detect")
        btn_detect.clicked.connect(self._redetect)
        gl.addWidget(btn_detect, 1,2)
        
        # Splash randomizer toggle
        self.randomizer_check = QCheckBox("Enable splash screen randomizer")
        self.randomizer_check.setChecked(self.randomizer_enabled)
        self.randomizer_check.stateChanged.connect(self._toggle_randomizer)
        gl.addWidget(self.randomizer_check, 2, 0, 1, 2)
        
        root.addWidget(g)

        # Show current theme path
        info_row = QHBoxLayout()
        info_row.addWidget(_label("Current theme:"))
        self.theme_lbl = _label(str(backend.OUR_THEME_TXT), "badge")
        info_row.addWidget(self.theme_lbl)
        info_row.addStretch()
        root.addLayout(info_row)

        root.addStretch()

    def _redetect(self):
        res = backend.detect_screen_resolution()
        idx = self.res_combo.findText(res)
        if idx < 0:
            self.res_combo.insertItem(1, res)
            idx = 1
        self.res_combo.setCurrentIndex(idx)
        self.status(f"Detected: {res}", True)

    def _toggle_randomizer(self):
        enabled = self.randomizer_check.isChecked()
        if enabled:
            w = Worker(backend.enable_splash_randomizer)
            def _on_enable(ok, msg, chk=self.randomizer_check):
                self.status(msg, ok)
                self.randomizer_enabled = ok
                if not ok:
                    chk.blockSignals(True)
                    chk.setChecked(False)
                    chk.blockSignals(False)
            w.signals.done.connect(_on_enable)
        else:
            w = Worker(backend.disable_splash_randomizer)
            def _on_disable(ok, msg, chk=self.randomizer_check):
                self.status(msg, ok)
                if ok:
                    self.randomizer_enabled = False
                else:
                    chk.blockSignals(True)
                    chk.setChecked(True)
                    chk.blockSignals(False)
            w.signals.done.connect(_on_disable)
        QThreadPool.globalInstance().start(w)

    def get_timeout(self) -> int:
        return self.timeout_spin.value()

    def get_resolution(self) -> str:
        return self.res_combo.currentText()

    def get_state(self) -> dict:
        return {"timeout": self.timeout_spin.value(), "resolution": self.res_combo.currentText()}

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — LOG
# ══════════════════════════════════════════════════════════════════════════════
class LogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24,20,24,20)
        lay.addWidget(_label("LOG", "heading"))
        lay.addWidget(_hline())
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        lay.addWidget(self.view, 1)
        btn_clear = QPushButton("Clear log")
        btn_clear.clicked.connect(self.view.clear)
        lay.addWidget(btn_clear)

    def append(self, msg: str, ok: bool = True):
        color = GREEN if ok else RED
        self.view.append(f'<span style="color:{color};">{msg}</span>')

# ══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GRUB Configurator")
        self.setMinimumSize(1100, 740)
        self._state = backend.load_state()
        self._screen_res = backend.detect_screen_resolution()
        self._cfg = ThemeConfig()
        saved_theme = self._state.get("theme_cfg", {})
        if saved_theme:
            self._cfg.from_dict(saved_theme)
        self._build()
        self.setStyleSheet(SS)

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        # header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background:{BG1};border-bottom:1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24,0,24,0)
        title = QLabel("GRUB CONFIGURATOR")
        title.setStyleSheet(f"color:{AMBER};font-size:16px;font-weight:bold;letter-spacing:3px;")
        hl.addWidget(title)
        hl.addStretch()
        res_lbl = QLabel(f"Screen: {self._screen_res}")
        res_lbl.setObjectName("sub")
        hl.addWidget(res_lbl)
        root.addWidget(header)

        # toast
        self.toast = Toast()
        root.addWidget(self.toast)

        # tabs
        self.tabs = QTabWidget()
        self.splash_tab   = SplashTab(self._status, self._state)
        self.themes_tab   = ThemesTab(self._cfg, self._status, self._screen_res)
        self.settings_tab = SettingsTab(self._status, self._screen_res, self._state)
        self.log_tab      = LogTab()

        self.tabs.addTab(self.splash_tab,   "💦  Splash Screen")
        self.tabs.addTab(self.themes_tab,   "🎨  Themes")
        self.tabs.addTab(self.settings_tab, "⚙  Settings")
        self.tabs.addTab(self.log_tab,      "📋  Log")
        self.tabs.setCurrentIndex(1)  # default: Themes

        root.addWidget(self.tabs, 1)

        # bottom bar
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{BG1};border-top:1px solid {BORDER};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(24,0,24,0)
        bl.setSpacing(12)

        self.progress = QProgressBar()
        self.progress.setRange(0,0)
        self.progress.setFixedWidth(160)
        self.progress.hide()
        bl.addWidget(self.progress)
        bl.addStretch()

        btn_preview = QPushButton("👁  Preview Theme")
        btn_preview.setObjectName("preview")
        btn_preview.setFixedHeight(38)
        btn_preview.clicked.connect(self._preview_theme)
        btn_preview.setStyleSheet(f"""
            QPushButton {{ background:{BG2}; color:{AMBER}; border:1px solid {AMBER}; border-radius:4px; padding:7px 16px; font-family:'JetBrains Mono','Fira Mono',monospace; font-size:12px; letter-spacing:1px; }}
            QPushButton:hover {{ background:{BG3}; border-color:{AMBER2}; color:{AMBER2}; }}
            QPushButton:pressed {{ background:{BG1}; color:{AMBER3}; border-color:{AMBER3}; }}
        """)
        bl.addWidget(btn_preview)

        btn_apply = QPushButton("▶  APPLY TO GRUB")
        btn_apply.setFixedHeight(38)
        btn_apply.setFixedWidth(180)
        btn_apply.clicked.connect(self._apply)
        btn_apply.setStyleSheet(f"""
            QPushButton {{ background:{BG2}; color:{AMBER}; border:1px solid {AMBER}; border-radius:4px; padding:7px 16px; font-family:'JetBrains Mono','Fira Mono',monospace; font-size:12px; letter-spacing:1px; }}
            QPushButton:hover {{ background:{BG3}; border-color:{AMBER2}; color:{AMBER2}; }}
            QPushButton:pressed {{ background:{BG1}; color:{AMBER3}; border-color:{AMBER3}; }}
        """)
        bl.addWidget(btn_apply)
        
        root.addWidget(bar)

    def _status(self, msg: str, ok: bool = True):
        self.toast.show_msg(msg, ok)
        self.log_tab.append(msg, ok)

    def _save_state(self):
        self.themes_tab.sync_all()
        state = {}
        state.update(self.settings_tab.get_state())
        state.update(self.splash_tab.get_state())
        state["theme_cfg"] = self._cfg.to_dict()
        backend.save_state(state)

    def closeEvent(self, e):
        self._save_state()
        super().closeEvent(e)

    def _busy(self, on: bool):
        self.progress.setVisible(on)

    def _apply(self):
        self._save_state()
        res     = self.settings_tab.get_resolution()
        timeout = self.settings_tab.get_timeout()
        self._busy(True)
        self._status("Applying — writing theme.txt and updating GRUB…", True)
        w = Worker(backend.full_apply, self._cfg, res, timeout)
        w.signals.done.connect(self._on_applied)
        QThreadPool.globalInstance().start(w)

    def _on_applied(self, ok: bool, msg: str):
        self._busy(False)
        if ok:
            self._status("✓ GRUB updated. Reboot to see changes.", True)
        else:
            self._status(f"Failed: {msg}", False)

    def _preview_theme(self):
        from pathlib import Path
        self.themes_tab.sync_all()
        ok, msg = backend.write_theme_txt(self._cfg)
        if not ok:
            self._status(f"Could not write theme for preview: {msg}", False)
            return

        # Use the robust backend detector
        tool = backend.find_preview_tool()
        if not tool:
            self._status(
                "No preview tool found. Install 'grub2-theme-preview' "
                "(pipx install grub2-theme-preview) or 'grub-emu'.", False
            )
            return

        tool_name = Path(tool).name
        self._status(f"Opening preview ({tool_name})…", True)

        w = Worker(backend.preview_theme, self._cfg, 10)
        w.signals.done.connect(lambda ok, msg: self._status(msg, ok))
        QThreadPool.globalInstance().start(w)

# ── Entry point ──────────────────────────────────────────────────────────────
def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("GRUB Configurator")
    for fam in ["JetBrains Mono", "Fira Mono", "Source Code Pro"]:
        if fam in QFontDatabase.families():
            app.setFont(QFont(fam, 11))
            break
    win = MainWindow()
    win.show()
    sys.exit(app.exec())