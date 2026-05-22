# Grub-Configurator
#### Video Demo:  <URL HERE>
#### Description:
A cross-distro PyQt6 GUI for managing GRUB2 themes, backgrounds, fonts, and Plymouth splash screens — with graphical privilege elevation via polkit, no terminal required.

---

## Features

- **GRUB Theme Editor** — live-edit background, boot menu, progress bar, countdown, subtitle, title image, and footer image with real-time theme.txt generation
- **Wallpaper Manager** — import and preview wallpapers directly in the UI
- **Font Builder** — convert system TTF/OTF fonts to GRUB `.pf2` format
- **Plymouth Splash Preview** — animated in-app preview of Plymouth boot themes, frame-by-frame at the theme's native FPS
- **GRUB Preview** — launch `grub2-theme-preview` for a live QEMU preview of your theme
- **Settings** — configure screen resolution and boot timeout written directly to `/etc/default/grub`
- **Graphical privilege prompt** — uses `pkexec` (polkit) for a GUI password dialog, falls back to `gksudo`/`kdesudo`/`xterm+sudo`
- **Cross-distro** — supports Debian/Ubuntu (apt) and Arch (pacman), EFI and legacy BIOS

---

## Screenshots

> Coming soon

---

## Requirements

- Python 3.10+
- PyQt6
- GRUB2
- Plymouth (for splash screen management)
- `grub2-theme-preview` (optional, for QEMU preview)

---

## Installation

```bash
git clone https://github.com/yourname/grub-configurator
cd grub-configurator
sudo ./install.sh
```

The installer will:
1. Optionally reset GRUB to factory defaults
2. Install system dependencies (`python3-pyqt6`, `grub-common`, `plymouth`, etc.)
3. Copy the app to `/opt/grub-configurator`
4. Create a launcher at `/usr/local/bin/grub-configurator`
5. Install the polkit policy for graphical privilege elevation
6. Install a sudoers drop-in to preserve display environment variables
7. Register the desktop entry

### Uninstall

```bash
sudo ./install.sh --uninstall
```

---

## Usage

Launch from your application menu or run:

```bash
grub-configurator
```

> Do **not** run with `sudo` — the app handles privilege elevation internally via a graphical polkit prompt.

### Tabs

| Tab | Description |
|-----|-------------|
| 💦 Splash Screen | Preview and set Plymouth boot splash themes |
| 🎨 Themes | Edit all GRUB theme elements |
| ⚙ Settings | Set resolution and timeout |
| 📋 Log | View operation history |

### Theme Editor Sub-tabs

| Sub-tab | Controls |
|---------|----------|
| 🖼 Background | Import and select wallpapers |
| 💬 Subtitle | Text label below the title |
| 📋 Boot Menu | Fonts, colors, icons, spacing |
| ⏳ Progress Bar | Timeout bar color and size |
| 🕐 Countdown | Remaining seconds text |
| 🏷 Title Image | Optional logo at the top |
| 🔻 Footer | Optional image at the bottom |

### GRUB Preview

Requires `grub2-theme-preview` installed via pipx:

```bash
pipx install grub2-theme-preview
```

---

## File Structure

```
grub-configurator/
├── main.py                          # Entry point, pkexec elevation
├── grub_preview.py                  # Standalone GRUB theme previewer
├── setup.py                         # Python package setup
├── install.sh                       # Universal installer/uninstaller
├── grub-configurator.desktop        # Desktop entry
├── com.github.grub-configurator.policy  # Polkit policy
├── grub_configurator/
│   ├── __init__.py
│   ├── backend.py                   # All system operations
│   └── gui.py                       # PyQt6 UI
└── grub_configurator_theme/         # Bundled default theme assets
    ├── theme.txt
    ├── selectedIcon_w.png
    ├── notSelectedIcon_w.png
    └── wallpapers/
```

---

## How It Works

1. Launched as a normal user, `main.py` calls `pkexec` to re-execute itself as root with display environment forwarded
2. As root, the PyQt6 GUI loads and all file writes go directly to system paths
3. Plymouth previews drop back to the real user via `sudo -u $REAL_USER env DISPLAY=... XAUTHORITY=...` to preserve X11 access
4. Theme changes are written to `/boot/grub/themes/grub-configurator/theme.txt`
5. Applying runs `update-grub` / `grub-mkconfig` automatically

---

## Distro Compatibility

| Distro | Status |
|--------|--------|
| Ubuntu / Pop!_OS | ✅ Tested |
| Debian | ⚠️ Not tested |
| Arch Linux | ⚠️ Not tested |
| Fedora | ⚠️ Not supported |

---

## License

MIT
