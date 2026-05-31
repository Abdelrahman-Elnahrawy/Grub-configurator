#!/usr/bin/env python3
"""
grub_configurator/backend.py
────────────────────────────
Theme-centric backend.

- All visual settings live in theme.txt.
- /etc/default/grub gets:
    * GRUB_THEME        → points to the generated theme
    * GRUB_GFXMODE      → screen resolution
    * GRUB_TIMEOUT      → menu timeout
    * GRUB_BACKGROUND   → covers the terminal box (absolute path)
- Fonts are compiled to /boot/grub/fonts/ and loaded globally via
  /etc/grub.d/00_fonts.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Paths & constants ────────────────────────────────────────────────────────
GRUB_DEFAULT_CFG   = Path("/etc/default/grub")
GRUB_THEMES_ROOT   = Path("/boot/grub/themes")
OUR_THEME_NAME     = "grub-configurator"
OUR_THEME_DIR      = GRUB_THEMES_ROOT / OUR_THEME_NAME
OUR_THEME_TXT      = OUR_THEME_DIR / "theme.txt"
OUR_WALLPAPERS_DIR = OUR_THEME_DIR / "wallpapers"
OUR_ICONS_DIR      = OUR_THEME_DIR / "icons"
OUR_FONTS_DIR      = Path("/boot/grub/fonts")          # global font location
FONT_LOADER_SCRIPT = Path("/etc/grub.d/00_fonts")      # auto‑loader

BUNDLED_THEME_DIR  = Path(__file__).parent.parent / "grub_configurator_theme"

SPLASH_DIRS        = [Path("/usr/share/plymouth/themes")]
STATE_FILE         = Path.home() / ".config" / "grub-configurator" / "state.json"
STATE_VERSION      = 1

UPDATE_GRUB_CMDS   = [
    ["update-grub"],
    ["grub2-mkconfig", "-o", "/boot/grub2/grub.cfg"],
    ["grub-mkconfig",  "-o", "/boot/grub/grub.cfg"],
]

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga"}
MAX_WALLPAPER_MB     = 10
ICON_MAX_PX          = 50


# ── Low‑level helpers ────────────────────────────────────────────────────────

def _run(cmd: list, sudo: bool = False) -> tuple[int, str, str]:
    """Run a command. The app is already root (via pkexec); `sudo` is optional."""
    if sudo:
        cmd = ["sudo"] + cmd
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _sudo_write(content: str, dest: Path) -> tuple[bool, str]:
    """Write content to a root‑owned path via a temp file + cp (no sudo)."""
    with tempfile.NamedTemporaryFile("w", suffix=".tmp", delete=False) as f:
        f.write(content)
        tmp = f.name
    rc, _, err = _run(["cp", tmp, str(dest)])
    os.unlink(tmp)
    if rc != 0:
        return False, err
    return True, str(dest)


def _update_grub() -> tuple[bool, str]:
    for cmd in UPDATE_GRUB_CMDS:
        if shutil.which(cmd[0]):
            rc, out, err = _run(cmd)   # no sudo – we are root
            return (True, out) if rc == 0 else (False, err)
    return False, "No update-grub command found."


# ── Screen resolution ────────────────────────────────────────────────────────

def detect_screen_resolution() -> str:
    """Try xrandr → wayland tools → DRM sysfs → Xorg log → fallback."""
    try:
        env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
        r = subprocess.run(["xrandr", "--current"], capture_output=True,
                           text=True, timeout=4, env=env)
        for line in r.stdout.splitlines():
            m = re.search(r"(\d{3,5})x(\d{3,5})\s+[\d.]+\*", line)
            if m:
                return f"{m.group(1)}x{m.group(2)}"
    except Exception:
        pass
    for cmd in [["wlr-randr"], ["kscreen-doctor", "-o"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            m = re.search(r"(\d{3,5})x(\d{3,5})", r.stdout)
            if m:
                return f"{m.group(1)}x{m.group(2)}"
        except Exception:
            pass
    drm = Path("/sys/class/drm")
    if drm.exists():
        for connector in sorted(drm.iterdir()):
            modes = connector / "modes"
            if modes.exists():
                try:
                    first = modes.read_text().strip().splitlines()[0]
                    m = re.match(r"(\d{3,5})x(\d{3,5})", first)
                    if m:
                        return f"{m.group(1)}x{m.group(2)}"
                except Exception:
                    pass
    try:
        text = Path("/var/log/Xorg.0.log").read_text(errors="ignore")
        for m in re.finditer(r"(\d{3,5})x(\d{3,5})", text):
            w, h = int(m.group(1)), int(m.group(2))
            if w >= 800 and h >= 600:
                return f"{w}x{h}"
    except Exception:
        pass
    return "1024x768"


def parse_resolution(res: str) -> tuple[int, int]:
    m = re.match(r"(\d+)x(\d+)", res)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def fmt_grub_resolution(res: str) -> str:
    if not res or res == "auto":
        return "auto"
    if re.match(r"^\d+x\d+$", res):
        return f"{res}x32,{res}x24,auto"
    return res


# ── /etc/default/grub manipulation ───────────────────────────────────────────

def _read_grub_default() -> dict:
    data = {}
    if not GRUB_DEFAULT_CFG.exists():
        return data
    for line in GRUB_DEFAULT_CFG.read_text().splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        v = v.strip().strip('"').strip("'")
        data[k.strip()] = v
    return data


def _write_grub_key(key: str, value: str) -> tuple[bool, str]:
    """Set or replace a key=value in /etc/default/grub (preserving other lines)."""
    if not GRUB_DEFAULT_CFG.exists():
        return False, "File not found"
    lines = GRUB_DEFAULT_CFG.read_text().splitlines()
    new_lines = []
    found = False
    pattern = re.compile(rf"^#?\s*{re.escape(key)}\s*=")
    for line in lines:
        if pattern.match(line):
            new_lines.append(f'{key}="{value}"')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'{key}="{value}"')
    return _sudo_write("\n".join(new_lines) + "\n", GRUB_DEFAULT_CFG)


def apply_grub_settings(theme_path: str, resolution: str, timeout: int,
                        background_path: Optional[str] = None) -> tuple[bool, str]:
    """Write GRUB_THEME, GRUB_GFXMODE, GRUB_TIMEOUT (and optionally GRUB_BACKGROUND).
       Also purges any old conflicting keys."""
    # 1. Remove keys that would overwrite our theme / background
    conflicting_keys = ["GRUB_BACKGROUND", "GRUB_FONT", "GRUB_THEME"]
    if GRUB_DEFAULT_CFG.exists():
        lines = GRUB_DEFAULT_CFG.read_text().splitlines()
        new_lines = []
        for line in lines:
            if any(re.match(rf"^#?\s*{re.escape(k)}\s*=", line) for k in conflicting_keys):
                continue
            new_lines.append(line)
        ok, msg = _sudo_write("\n".join(new_lines) + "\n", GRUB_DEFAULT_CFG)
        if not ok:
            return False, f"Could not clean old settings: {msg}"

    # 2. Write our clean keys
    for key, val in [
        ("GRUB_THEME",           theme_path),
        ("GRUB_GFXMODE",         fmt_grub_resolution(resolution)),
        ("GRUB_GFXPAYLOAD_LINUX","keep"),
        ("GRUB_TIMEOUT",         str(timeout)),
        ("GRUB_TERMINAL_OUTPUT", "gfxterm"),
    ]:
        ok, msg = _write_grub_key(key, val)
        if not ok:
            return False, f"Could not set {key}: {msg}"

    # 3. Set the global background image if provided
    if background_path and Path(background_path).exists():
        ok, msg = _write_grub_key("GRUB_BACKGROUND", background_path)
        if not ok:
            return False, f"Could not set GRUB_BACKGROUND: {msg}"

    return _update_grub()


def get_grub_timeout() -> int:
    try:
        return int(_read_grub_default().get("GRUB_TIMEOUT", "10"))
    except ValueError:
        return 10


def get_grub_resolution() -> str:
    raw = _read_grub_default().get("GRUB_GFXMODE", "auto")
    return raw.split(",")[0].split("x32")[0] if raw != "auto" else "auto"


# ── Theme directory bootstrap ────────────────────────────────────────────────

def ensure_theme_dirs() -> tuple[bool, str]:
    """Create the theme tree and copy bundled icons (if missing)."""
    for d in [OUR_THEME_DIR, OUR_WALLPAPERS_DIR, OUR_ICONS_DIR]:
        rc, _, err = _run(["mkdir", "-p", str(d)])
        if rc != 0:
            return False, f"mkdir {d}: {err}"

    if BUNDLED_THEME_DIR.exists():
        for icon_name in ["selectedIcon_w.png", "notSelectedIcon_w.png"]:
            src = BUNDLED_THEME_DIR / icon_name
            dst = OUR_ICONS_DIR / icon_name
            if src.exists() and not dst.exists():
                _run(["cp", str(src), str(dst)])
    return True, "OK"


# ── Wallpaper management ─────────────────────────────────────────────────────

def list_wallpapers() -> list[Path]:
    if not OUR_WALLPAPERS_DIR.exists():
        return []
    return sorted(
        p for p in OUR_WALLPAPERS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS
    )


def import_wallpaper(src: Path, screen_res: str) -> tuple[bool, str]:
    """Copy an image to the wallpapers folder, performing basic sanity checks."""
    if src.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
        return False, f"Unsupported format: {src.suffix}"
    size_mb = src.stat().st_size / (1024 * 1024)
    if size_mb > MAX_WALLPAPER_MB:
        return False, f"File too large: {size_mb:.1f} MB (max {MAX_WALLPAPER_MB} MB)"

    warning = ""
    img_res = _get_image_resolution(src)
    if img_res and screen_res and img_res != screen_res:
        warning = f" (warning: image is {img_res}, screen is {screen_res})"

    dest = OUR_WALLPAPERS_DIR / src.name
    try:
        shutil.copy2(src, dest)
    except OSError as e:
        return False, str(e)
    return True, f"Imported {src.name}{warning}"


def _get_image_resolution(path: Path) -> str:
    """Probe PNG/JPEG dimensions without external libraries."""
    try:
        with open(path, "rb") as f:
            sig = f.read(8)
            if sig == b"\x89PNG\r\n\x1a\n":
                f.read(4)
                f.read(4)
                import struct
                w, h = struct.unpack(">II", f.read(8))
                return f"{w}x{h}"
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            import struct
            data = f.read()
        i = 2
        while i < len(data) - 8:
            marker = data[i:i+2]
            length = struct.unpack(">H", data[i+2:i+4])[0]
            if marker[0] == 0xFF and marker[1] in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i+5:i+9])
                return f"{w}x{h}"
            i += 2 + length
    except Exception:
        pass
    return ""


# ── Icon management ──────────────────────────────────────────────────────────

def _get_png_size(path: Path) -> tuple[int, int]:
    try:
        import struct
        with open(path, "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return 0, 0
            f.read(4)
            f.read(4)
            w, h = struct.unpack(">II", f.read(8))
            return w, h
    except Exception:
        return 0, 0


def import_icon(src: Path, kind: str) -> tuple[bool, str]:
    """Validate and copy a PNG icon. Icons must be ≤ ICON_MAX_PX in both dimensions,
       and both selected/notselected icons must have the same size."""
    if src.suffix.lower() != ".png":
        return False, "Icons must be PNG files"
    w, h = _get_png_size(src)
    if w == 0:
        return False, "Could not read dimensions"
    if w > ICON_MAX_PX or h > ICON_MAX_PX:
        return False, f"Icon too large: {w}×{h} (max {ICON_MAX_PX}px)"

    other_kind   = "notselected" if kind == "selected" else "selected"
    other_fname  = f"{other_kind}Icon_w.png"
    other_path   = OUR_ICONS_DIR / other_fname
    if other_path.exists():
        ow, oh = _get_png_size(other_path)
        if (ow, oh) != (w, h):
            return False, (
                f"Size mismatch: new icon is {w}×{h} but "
                f"{other_fname} is {ow}×{oh}. Both icons must be the same size."
            )

    fname = f"{kind}Icon_w.png"
    dest  = OUR_ICONS_DIR / fname
    try:
        shutil.copy2(src, dest)
    except OSError as e:
        return False, str(e)
    return True, f"Icon '{fname}' installed ({w}×{h})"


# ── Font management (global .pf2 in /boot/grub/fonts) ────────────────────────

def list_system_fonts() -> list[tuple[str, Path]]:
    font_dirs = [Path("/usr/share/fonts"), Path.home() / ".fonts",
                 Path.home() / ".local/share/fonts"]
    results = []
    seen_names = set()
    for d in font_dirs:
        if not d.exists():
            continue
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() in (".ttf", ".otf") and f.is_file():
                name = f.stem.replace("-", " ").replace("_", " ")
                if name not in seen_names:
                    seen_names.add(name)
                    results.append((name, f))
    return results


def build_pf2_font(ttf_path: Path, size: int, font_name: str) -> tuple[bool, str]:
    """Convert a TTF/OTF to .pf2 and store it in /boot/grub/fonts/.
       Automatically updates /etc/grub.d/00_fonts."""
    if not shutil.which("grub-mkfont"):
        return False, "grub-mkfont not found"

    OUR_FONTS_DIR.mkdir(parents=True, exist_ok=True)

    safe = re.sub(r"[^A-Za-z0-9_-]", "_", font_name)
    out_name = f"{safe}_{size}.pf2"
    tmp_out  = Path("/tmp") / out_name

    proc = subprocess.run(
        ["grub-mkfont", "-s", str(size), "-o", str(tmp_out), str(ttf_path)],
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        return False, proc.stderr

    dest = OUR_FONTS_DIR / out_name
    try:
        shutil.copy2(tmp_out, dest)
    except OSError as e:
        return False, str(e)
    tmp_out.unlink(missing_ok=True)

    # Update the loader script that loads all .pf2 files at boot
    _update_font_loader_script()
    return True, f"{font_name} {size}"


def _update_font_loader_script() -> tuple[bool, str]:
    """(Re)create /etc/grub.d/00_fonts that loads all .pf2 files from /boot/grub/fonts.
       If no .pf2 files remain, the script is removed."""
    if not OUR_FONTS_DIR.exists():
        return True, "No fonts directory yet"

    lines = ["#!/bin/sh", "exec tail -n +3 $0"]
    for pf in sorted(OUR_FONTS_DIR.glob("*.pf2")):
        lines.append(f'loadfont {pf}')

    if len(lines) == 2:
        # No custom fonts – remove loader script
        if FONT_LOADER_SCRIPT.exists():
            FONT_LOADER_SCRIPT.unlink()
        return True, "OK"

    content = "\n".join(lines) + "\n"
    try:
        FONT_LOADER_SCRIPT.write_text(content)
        FONT_LOADER_SCRIPT.chmod(0o755)
    except OSError as e:
        return False, str(e)
    return True, "Font loader script updated"


# ── Theme configuration & theme.txt generator ────────────────────────────────

class ThemeConfig:
    """Pure‑data model of our theme.txt. Serialisable and renderable."""

    def __init__(self):
        # Global
        self.background_file: str = "wallpapers/1.png"   # relative to theme dir
        self.terminal_font:   str = "unicode"
        self.terminal_left:   str = "0%"
        self.terminal_top:    str = "0%"
        self.terminal_width:  str = "100%"
        self.terminal_height: str = "100%"

        # Title image (disabled by default)
        self.title_image_enabled: bool  = False
        self.title_image_file:    str   = ""
        self.title_image_left:    str   = "0%"
        self.title_image_top:     str   = "0%"

        # Subtitle label
        self.subtitle_enabled: bool = True
        self.subtitle_text:    str  = " "
        self.subtitle_font:    str  = "unicode"
        self.subtitle_color:   str  = "#a0c4ff"
        self.subtitle_left:    str  = "10%"
        self.subtitle_top:     str  = "17%"
        self.subtitle_width:   str  = "80%"
        self.subtitle_height:  int  = 40
        self.subtitle_align:   str  = "center"

        # Boot menu
        self.menu_left:              str  = "3%"
        self.menu_top:               str  = "72%"
        self.menu_width:             str  = "60%"
        self.menu_height:            str  = "10%"
        self.menu_item_font:         str  = "unicode"
        self.menu_selected_font:     str  = "unicode"
        self.menu_item_color:        str  = "#919090"
        self.menu_selected_color:    str  = "#ffffff"
        self.menu_icon_width:        int  = 14
        self.menu_icon_height:       int  = 14
        self.menu_icon_space:        int  = 0
        self.menu_item_height:       int  = 36
        self.menu_item_padding:      int  = 0
        self.menu_item_spacing:      int  = 10
        self.menu_scrollbar:         bool = False
        self.menu_selected_icon:     str  = "icons/selectedIcon_*.png"
        self.menu_notselected_icon:  str  = "icons/notSelectedIcon_*.png"

        # Progress bar
        self.progress_enabled:      bool = True
        self.progress_left:         str  = "25%"
        self.progress_top:          str  = "78%"
        self.progress_width:        str  = "50%"
        self.progress_height:       int  = 1
        self.progress_fg_color:     str  = "#c9a84c"
        self.progress_bg_color:     str  = "#1a1a2e"
        self.progress_border_color: str  = "#a67c00"
        self.progress_font:         str  = "unicode"

        # Countdown label
        self.countdown_enabled: bool = True
        self.countdown_left:    str  = "25%"
        self.countdown_top:     str  = "84%"
        self.countdown_width:   str  = "50%"
        self.countdown_height:  int  = 28
        self.countdown_color:   str  = "#7788aa"
        self.countdown_font:    str  = "unicode"
        self.countdown_align:   str  = "center"

        # Footer image
        self.footer_image_enabled: bool = False
        self.footer_image_file:    str  = ""
        self.footer_image_left:    str  = "0%"
        self.footer_image_top:     str  = "92%"

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def from_dict(self, d: dict):
        for k, v in d.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def render(self) -> str:
        """Generate the complete theme.txt content."""
        def c(flag: bool, block: str) -> str:
            if flag:
                return block
            return "\n".join(
                f"# {line}" if line.strip() else line
                for line in block.splitlines()
            )

        sb = f"""
# ============================================================
#   GRUB Theme — generated by GRUB Configurator
# ============================================================

# --- Global ---
desktop-image: "{self.background_file}"
title-text: ""
terminal-font: "{self.terminal_font}"
terminal-left:   "0%"
terminal-top:    "0%"
terminal-width:  "100%"
terminal-height: "100%"
terminal-border: "0"

# ============================================================
# TITLE IMAGE
# ============================================================
"""
        title_block = f"""+ image {{
    left = {self.title_image_left}
    top  = {self.title_image_top}
    file = "{self.title_image_file}"
}}"""
        sb += c(self.title_image_enabled, title_block) + "\n"

        sb += """
# ============================================================
# SUBTITLE LABEL
# ============================================================
"""
        sub_block = f"""+ label {{
    left   = {self.subtitle_left}
    top    = {self.subtitle_top}
    width  = {self.subtitle_width}
    height = {self.subtitle_height}
    text  = "{self.subtitle_text}"
    font  = "{self.subtitle_font}"
    color = "{self.subtitle_color}"
    align = "{self.subtitle_align}"
    bg_color = "#00000000"
}}"""
        sb += c(self.subtitle_enabled, sub_block) + "\n"

        sb += """
# ============================================================
# BOOT MENU
# ============================================================
"""
        menu_scrollbar = "false" if not self.menu_scrollbar else "true"
        sb += f"""+ boot_menu {{
    left   = {self.menu_left}
    top    = {self.menu_top}
    width  = {self.menu_width}
    height = {self.menu_height}
    item_font          = "{self.menu_item_font}"
    selected_item_font = "{self.menu_selected_font}"
    item_color          = "{self.menu_item_color}"
    selected_item_color = "{self.menu_selected_color}"
    icon_width      = {self.menu_icon_width}
    icon_height     = {self.menu_icon_height}
    item_icon_space = {self.menu_icon_space}
    item_height  = {self.menu_item_height}
    item_padding = {self.menu_item_padding}
    item_spacing = {self.menu_item_spacing}
    selected_item_pixmap_style = "{self.menu_selected_icon}"
    item_pixmap_style          = "{self.menu_notselected_icon}"
    scrollbar = {menu_scrollbar}
}}
"""

        sb += """
# ============================================================
# PROGRESS BAR — timeout countdown
# ============================================================
"""
        prog_block = f"""+ progress_bar {{
    id     = "__timeout__"
    left   = {self.progress_left}
    top    = {self.progress_top}
    width  = {self.progress_width}
    height = {self.progress_height}
    fg_color     = "{self.progress_fg_color}"
    bg_color     = "{self.progress_bg_color}"
    border_color = "{self.progress_border_color}"
    font       = "{self.progress_font}"
    color = "{self.countdown_color}"
}}"""
        sb += c(self.progress_enabled, prog_block) + "\n"

        sb += """
# ============================================================
# COUNTDOWN LABEL
# ============================================================
"""
        cd_block = f"""+ label {{
    id     = "__timeout__"
    left   = {self.countdown_left}
    top    = {self.countdown_top}
    width  = {self.countdown_width}
    height = {self.countdown_height}
    text  = "Automatic boot in %d seconds..."    color = "{self.countdown_color}"
    font  = "{self.countdown_font}"
    align = "{self.countdown_align}"
    bg_color = "#00000000"
}}"""
        sb += c(self.countdown_enabled, cd_block) + "\n"

        sb += """
# ============================================================
# FOOTER IMAGE
# ============================================================
"""
        footer_block = f"""+ image {{
    left = {self.footer_image_left}
    top  = {self.footer_image_top}
    file = "{self.footer_image_file}"
}}"""
        sb += c(self.footer_image_enabled, footer_block) + "\n"

        return sb


# ── Write theme operations ───────────────────────────────────────────────────

def write_theme_txt(cfg: ThemeConfig) -> tuple[bool, str]:
    ok, msg = ensure_theme_dirs()
    if not ok:
        return False, msg
    return _sudo_write(cfg.render(), OUR_THEME_TXT)


def full_apply(cfg: ThemeConfig, resolution: str, timeout: int) -> tuple[bool, str]:
    """Write theme.txt → update /etc/default/grub (incl. background) → update-grub."""
    ok, msg = write_theme_txt(cfg)
    if not ok:
        return False, f"theme.txt write failed: {msg}"

    # Ensure global font loader is up-to-date
    _update_font_loader_script()

    # Compute absolute path to the selected background for GRUB_BACKGROUND
    bg_full = OUR_THEME_DIR / cfg.background_file
    bg_abs = str(bg_full.resolve()) if bg_full.exists() else None

    # Copy icons to theme root so GRUB can find glob patterns
    for icon in ["selectedIcon_w.png", "notSelectedIcon_w.png"]:
        src = OUR_ICONS_DIR / icon
        if src.exists():
            _run(["cp", str(src), str(OUR_THEME_DIR / icon)])

    return apply_grub_settings(
        str(OUR_THEME_TXT),
        resolution,
        timeout,
        background_path=bg_abs
    )
def get_plymouth_theme_frames(theme_name: str) -> tuple[list[Path], float]:
    """
    Returns (ordered list of frame images, fps) for a Plymouth theme.
    Parses the .script file for the frame rate; falls back to 16 fps.
    Supports sprite-sheet themes (spinner etc) and multi-image themes.
    """
    theme_dir = Path("/usr/share/plymouth/themes") / theme_name
    if not theme_dir.exists():
        return [], 16.0

    # ── Parse fps from .script ────────────────────────────────────────
    fps = 16.0
    for script in theme_dir.glob("*.script"):
        try:
            text = script.read_text(errors="ignore")
            # Plymouth scripts use: Plymouth.SetRefreshRate(N)  or  refresh_rate = N
            m = re.search(r"SetRefreshRate\s*\(\s*(\d+(?:\.\d+)?)\s*\)", text)
            if not m:
                m = re.search(r"refresh.rate\s*=\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
            if m:
                fps = float(m.group(1))
                break
        except Exception:
            pass

    # ── Collect frame images ──────────────────────────────────────────
    image_exts = {".png", ".jpg", ".jpeg"}

    # Strategy 1: numbered sequence  (e.g. throbber-0000.png … throbber-0059.png)
    all_imgs = sorted(
        (p for p in theme_dir.rglob("*") if p.suffix.lower() in image_exts and p.is_file()),
        key=lambda p: (p.stem, p.name)
    )

    # Group by prefix (strip trailing digits)
    from itertools import groupby
    import re as _re
    def _base(p: Path) -> str:
        return _re.sub(r"[\-_]?\d+$", "", p.stem)

    groups: dict[str, list[Path]] = {}
    for img in all_imgs:
        groups.setdefault(_base(img), []).append(img)

    # Pick the largest numbered sequence (most likely the animation frames)
    if groups:
        frames = max(groups.values(), key=len)
        if len(frames) > 1:
            return sorted(frames), fps

    # Strategy 2: just return all images sorted (single logo etc.)
    return all_imgs, fps

# ── Plymouth (splash screen) ─────────────────────────────────────────────────

PLYMOUTH_BIN_DIRS = [
    Path("/usr/sbin"),
    Path("/usr/bin"),
    Path("/sbin"),
]

def _find_plymouth_set_theme() -> Optional[Path]:
    for d in PLYMOUTH_BIN_DIRS:
        candidate = d / "plymouth-set-default-theme"
        if candidate.exists():
            return candidate
    return None


def list_plymouth_themes() -> list[str]:
    themes = []
    for d in SPLASH_DIRS:
        if d.exists():
            themes += [
                p.name for p in d.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ]
    return sorted(set(themes))


def get_active_plymouth_theme() -> str:
    try:
        link = Path("/usr/share/plymouth/themes/default.plymouth")
        if link.is_symlink():
            # e.g. /usr/share/plymouth/themes/spinner/spinner.plymouth -> "spinner"
            return link.resolve().parent.name
    except Exception:
        pass
    return ""

def set_plymouth_theme(theme_name: str) -> tuple[bool, str]:
    exe = _find_plymouth_set_theme()
    if exe:
        try:
            subprocess.run([str(exe), "-R", theme_name], check=True, capture_output=True)
            return True, f"Plymouth theme set to '{theme_name}'"
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode() if e.stderr else str(e)
            return False, err

    # Fallback for Debian/Ubuntu: update-alternatives
    alternatives = shutil.which("update-alternatives")
    if alternatives and Path("/usr/share/plymouth/themes").exists():
        try:
            theme_file = f"/usr/share/plymouth/themes/{theme_name}/{theme_name}.plymouth"
            symlink = "/usr/share/plymouth/themes/default.plymouth"

            # Register theme as alternative if not already listed
            result = subprocess.run(
                [alternatives, "--list", "default.plymouth"],
                capture_output=True, text=True
            )
            registered = result.stdout.strip().splitlines()
            if theme_file not in registered:
                subprocess.run(
                    [alternatives, "--install", symlink, "default.plymouth", theme_file, "60"],
                    check=True
                )

            subprocess.run(
                [alternatives, "--set", "default.plymouth", theme_file],
                check=True
            )
            subprocess.run(["update-initramfs", "-u"], check=True)
            return True, f"Plymouth theme set to '{theme_name}' (via update-alternatives)"
        except subprocess.CalledProcessError as e:
            return False, str(e)
    return False, "No Plymouth set-default mechanism found."
def find_preview_tool() -> Optional[str]:
    """
    Locate grub2-theme-preview, grub2-emu, or grub-emu.
    Searches PATH and absolute directories, including ~/.local/bin
    of the real user when running under sudo.
    """
    names = ("grub2-theme-preview", "grub2-emu", "grub-emu")

    # PATH lookup
    for name in names:
        path = shutil.which(name)
        if path:
            return path

    # Fallback directories (pkexec strips PATH)
    real_user = os.environ.get("SUDO_USER") or os.environ.get("USER") or ""
    dirs = [
        "/usr/bin",
        "/usr/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
        "/sbin",
        "/bin",
        os.path.expanduser("~/.local/bin"),
    ]
    if real_user:
        dirs.append(f"/home/{real_user}/.local/bin")

    for d in dirs:
        for name in names:
            full = os.path.join(d, name)
            if os.path.isfile(full) and os.access(full, os.X_OK):
                return full
    return None
def preview_plymouth(theme_name: str, duration: int = 8) -> tuple[bool, str]:
    """
    Show Plymouth theme frames animated in a tkinter window,
    at the theme's real refresh rate, running as the real user.
    """
    frames, fps = get_plymouth_theme_frames(theme_name)
    if not frames:
        return False, f"No images found in theme '{theme_name}'"

    # Write a tiny self-contained animator script to /tmp
    frame_list = [str(f) for f in frames]
    animator_src = f"""\
#!/usr/bin/env python3
import tkinter as tk
from pathlib import Path

frames_paths = {frame_list!r}
fps          = {fps}
duration     = {duration}

try:
    from PIL import Image, ImageTk
    use_pil = True
except ImportError:
    use_pil = False

root = tk.Tk()
root.title("Plymouth Preview — {theme_name}")
root.configure(bg="black")
root.resizable(False, False)

# Load frames
photos = []
if use_pil:
    for p in frames_paths:
        try:
            img = Image.open(p).convert("RGBA")
            photos.append(ImageTk.PhotoImage(img))
        except Exception:
            pass
else:
    for p in frames_paths:
        try:
            photos.append(tk.PhotoImage(file=p))
        except Exception:
            pass

if not photos:
    import sys
    print("No frames could be loaded")
    sys.exit(1)

# Fit window to first frame
w, h = photos[0].width(), photos[0].height()
canvas = tk.Canvas(root, width=w, height=h, bg="black", highlightthickness=0)
canvas.pack()
item = canvas.create_image(w//2, h//2, image=photos[0])

idx = [0]
total_frames = int(fps * duration)
shown = [0]

def next_frame():
    if shown[0] >= total_frames:
        root.destroy()
        return
    canvas.itemconfig(item, image=photos[idx[0] % len(photos)])
    idx[0] += 1
    shown[0] += 1
    root.after(int(1000 / fps), next_frame)

root.after(0, next_frame)
root.mainloop()
"""

    import tempfile
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="plymouth_preview_"
    )
    tmp.write(animator_src)
    tmp.close()
    os.chmod(tmp.name, 0o644)

    # Resolve real user — pkexec sets GRUB_REAL_USER (forwarded from USER before elevation)
    real_user = os.environ.get("SUDO_USER") or os.environ.get("GRUB_REAL_USER") or ""

    # Use the environment as-is — DISPLAY and XAUTHORITY are forwarded by pkexec env
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")

    if real_user and os.getuid() == 0:
        cmd = [
            "sudo", "-u", real_user,
            "env",
            f"DISPLAY={env.get('DISPLAY', ':0')}",
            f"XAUTHORITY={env.get('XAUTHORITY', '')}",
            sys.executable, tmp.name,
        ]
    else:
        cmd = [sys.executable, tmp.name]

    try:
        subprocess.Popen(cmd, env=env)
        return True, f"Plymouth preview launched ({len(frames)} frames @ {fps:.0f} fps)"
    except Exception as e:
        return False, str(e)
    finally:
        pass

def _find_grub_module_dir() -> Optional[Path]:
    grub_probe = shutil.which("grub-probe")
    platform = None
    if grub_probe:
        try:
            platform = subprocess.check_output(
                [grub_probe, "-t", "platform", "/"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except subprocess.CalledProcessError:
            pass
    if not platform:
        platform = "x86_64-efi" if Path("/sys/firmware/efi").exists() else "i386-pc"

    for d in [
        Path(f"/usr/lib/grub/{platform}"),
        Path(f"/usr/share/grub/{platform}"),
        Path(f"/lib/grub/{platform}"),
        Path(f"/boot/grub/{platform}"),
    ]:
        if d.is_dir() and any(d.glob("*.mod")):
            return d
    return None

# ── Theme preview (grub2‑emu) ────────────────────────────────────────────────

def preview_theme(cfg: ThemeConfig, duration: int = 10) -> tuple[bool, str]:
    # 1. Write theme.txt so the preview shows current settings
    ok, msg = write_theme_txt(cfg)
    if not ok:
        return False, msg

    # 2. Find grub_preview.py — sits next to this file
    preview_script = Path(__file__).parent.parent / "grub_preview.py"
    if not preview_script.exists():
        return False, f"grub_preview.py not found at {preview_script}"

    # 3. Find the real user to run it as (not root)
    real_user = os.environ.get("SUDO_USER") or os.environ.get("PKEXEC_UID") or ""
    if real_user and real_user.isdigit():
        import pwd
        try:
            real_user = pwd.getpwuid(int(real_user)).pw_name
        except Exception:
            real_user = ""

    # 4. Build display environment
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    if real_user:
        xauth = Path(f"/home/{real_user}/.Xauthority")
        if xauth.exists():
            env["XAUTHORITY"] = str(xauth)

    # 5. Launch as the real user so X11 permissions work
    if real_user and os.getuid() == 0:
        cmd = ["sudo", "-u", real_user, sys.executable,
               str(preview_script), str(OUR_THEME_DIR)]
    else:
        cmd = [sys.executable, str(preview_script), str(OUR_THEME_DIR)]

def preview_theme(cfg: ThemeConfig, duration: int = 10) -> tuple[bool, str]:
    ok, msg = write_theme_txt(cfg)
    if not ok:
        return False, msg

    preview_script = Path(__file__).parent.parent / "grub_preview.py"
    if not preview_script.exists():
        return False, f"grub_preview.py not found at {preview_script}"

    real_user = os.environ.get("SUDO_USER") or os.environ.get("PKEXEC_UID") or ""
    if real_user and real_user.isdigit():
        import pwd
        try:
            real_user = pwd.getpwuid(int(real_user)).pw_name
        except Exception:
            real_user = ""

    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    if real_user:
        xauth = Path(f"/home/{real_user}/.Xauthority")
        if xauth.exists():
            env["XAUTHORITY"] = str(xauth)

    if real_user and os.getuid() == 0:
        cmd = ["sudo", "-u", real_user, sys.executable,
               str(preview_script), str(OUR_THEME_DIR)]
    else:
        cmd = [sys.executable, str(preview_script), str(OUR_THEME_DIR)]

    try:
        import tempfile
        log_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, prefix="grub_preview_"
        )
        log.info("Preview cmd: %s", cmd)
        log.info("Preview env DISPLAY: %s", env.get("DISPLAY"))
        log.info("Preview env XAUTHORITY: %s", env.get("XAUTHORITY"))
        log.info("real_user resolved to: %r", real_user)
        log.info("preview_script exists: %s", preview_script.exists())
        proc = subprocess.Popen(
            cmd, env=env,
            stdout=log_file, stderr=log_file
        )
        log.info("Launched PID %d, log at %s", proc.pid, log_file.name)
        return True, f"Preview launched. Log: {log_file.name}"
    except Exception as e:
        return False, str(e)
# ── State persistence ────────────────────────────────────────────────────────

def load_state() -> dict:
    try:
        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
            version = state.get("_version")
            if version is None:
                # Legacy state format: preserve existing values and upgrade in-place.
                state["_version"] = STATE_VERSION
                try:
                    STATE_FILE.write_text(json.dumps(state, indent=2))
                except Exception:
                    pass
                return state
            if version != STATE_VERSION:
                log.info("State version mismatch — resetting to defaults")
                STATE_FILE.unlink()
                return {}
            return state
    except Exception as e:
        log.warning("Could not load state: %s", e)
    return {}


def save_state(state: dict) -> bool:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state["_version"] = STATE_VERSION
        STATE_FILE.write_text(json.dumps(state, indent=2))
        return True
    except Exception as e:
        log.error("Could not save state: %s", e)
        return False


# ── Splash randomizer service ────────────────────────────────────────────────
#
# Design notes:
#   • The randomizer runs as a SYSTEM-level systemd service (not --user).
#     The app runs as root via pkexec, so --user would point at root's session
#     which is never lingering — the service would never actually start at boot.
#   • The bash script lives at /usr/local/lib/grub-configurator/grub-splash-randomizer.
#   • The service unit lives at /etc/systemd/system/grub-splash-randomizer.service.
#   • Favourites are written to /etc/grub-configurator/state.json (system-wide)
#     so the script (running as root at boot, with no user session) can read them.

_RANDOMIZER_SCRIPT_DEST = Path("/usr/local/lib/grub-configurator/grub-splash-randomizer")
_RANDOMIZER_SCRIPT_SRC  = Path(__file__).parent.parent / "grub-splash-randomizer"
_SERVICE_UNIT_DEST      = Path("/etc/systemd/system/grub-splash-randomizer.service")
_SERVICE_UNIT_SRC       = Path(__file__).parent.parent / "grub-splash-randomizer.service"
_SYSTEM_STATE_FILE      = Path("/etc/grub-configurator/state.json")


def sync_favorites_to_system(favorites: list[str]) -> tuple[bool, str]:
    """
    Write the current favourites list into the system-wide state file at
    /etc/grub-configurator/state.json so the boot-time randomizer script
    (which runs as root with no user session) can read it.
    Called automatically whenever favourites change in the GUI.
    """
    try:
        _SYSTEM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if _SYSTEM_STATE_FILE.exists():
            try:
                existing = json.loads(_SYSTEM_STATE_FILE.read_text())
            except Exception:
                existing = {}
        existing["splash_favorites"] = favorites
        _SYSTEM_STATE_FILE.write_text(json.dumps(existing, indent=2))
        return True, f"Favourites synced to {_SYSTEM_STATE_FILE}"
    except Exception as e:
        return False, str(e)


def is_splash_randomizer_enabled() -> bool:
    """Return True when the system service is enabled (will run at next boot)."""
    try:
        r = subprocess.run(
            ["systemctl", "is-enabled", "grub-splash-randomizer.service"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() == "enabled"
    except Exception as e:
        log.warning("Could not check randomizer status: %s", e)
        return False


def enable_splash_randomizer() -> tuple[bool, str]:
    """
    Install the randomizer script + service unit and enable the system service.
    The service runs once at each boot (Type=oneshot, WantedBy=multi-user.target).
    Requires root (the app is already running as root via pkexec).
    """
    # 1. Install the bash script
    if not _RANDOMIZER_SCRIPT_SRC.exists():
        return False, (
            f"Randomizer script not found at {_RANDOMIZER_SCRIPT_SRC}. "
            "Make sure grub-splash-randomizer is present in the app directory."
        )
    try:
        _RANDOMIZER_SCRIPT_DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_RANDOMIZER_SCRIPT_SRC, _RANDOMIZER_SCRIPT_DEST)
        _RANDOMIZER_SCRIPT_DEST.chmod(0o755)
    except OSError as e:
        return False, f"Could not install randomizer script: {e}"

    # 2. Install the service unit
    if not _SERVICE_UNIT_SRC.exists():
        return False, (
            f"Service unit not found at {_SERVICE_UNIT_SRC}. "
            "Make sure grub-splash-randomizer.service is present in the app directory."
        )
    try:
        shutil.copy2(_SERVICE_UNIT_SRC, _SERVICE_UNIT_DEST)
        _SERVICE_UNIT_DEST.chmod(0o644)
    except OSError as e:
        return False, f"Could not install service unit: {e}"

    # 3. Reload systemd and enable the service
    try:
        subprocess.run(["systemctl", "daemon-reload"],
                       check=True, capture_output=True)
        subprocess.run(["systemctl", "enable", "grub-splash-randomizer.service"],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="replace").strip() if e.stderr else str(e)
        return False, f"systemctl failed: {err}"

    return True, "Splash randomizer enabled — a random favourite will be set on each boot."


def disable_splash_randomizer() -> tuple[bool, str]:
    """
    Disable and remove the system service.
    Leaves the script in place so re-enabling is instant.
    """
    try:
        subprocess.run(["systemctl", "disable", "grub-splash-randomizer.service"],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="replace").strip() if e.stderr else str(e)
        return False, f"Could not disable service: {err}"
    except Exception as e:
        return False, str(e)

    return True, "Splash randomizer disabled."
