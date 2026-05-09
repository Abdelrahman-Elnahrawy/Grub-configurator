#!/usr/bin/env python3
"""
grub-configurator — entry point
────────────────────────────────
Launches a graphical polkit/pkexec privilege prompt (like Grub Customizer),
then re-executes itself as root with the display environment preserved.
"""

import logging
import os
import sys
import subprocess
import shutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("Main")

POLKIT_ACTION = "com.github.grub-configurator.run"


def _preserve_display_env():
    """Ensure Qt-critical display vars survive elevation."""
    os.environ.setdefault("DISPLAY", ":0")

    if "XAUTHORITY" not in os.environ:
        candidate = os.path.join(os.path.expanduser("~"), ".Xauthority")
        if os.path.exists(candidate):
            os.environ["XAUTHORITY"] = candidate

    if "XDG_RUNTIME_DIR" not in os.environ:
        candidate = f"/run/user/{os.getuid()}"
        if os.path.isdir(candidate):
            os.environ["XDG_RUNTIME_DIR"] = candidate

    # Suppress harmless wayland-not-found noise
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland=false")
    # Prefer xcb when running as root (Wayland socket is user-session-only)
    if os.getuid() == 0:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def _elevate_via_pkexec():
    """
    Re-launch this script under pkexec, forwarding the display environment.
    pkexec reads the polkit policy and shows the graphical password dialog.
    Returns True if elevation succeeded (we are now root), False if failed.
    """
    if not shutil.which("pkexec"):
        log.warning("pkexec not found — falling back to gksudo/sudo")
        return _elevate_fallback()
    real_user = os.environ.get("SUDO_USER") or os.environ.get("USER") or ""
    # Pass display vars explicitly — pkexec allowlist is in the .policy file
    env_fwd = [
        f"DISPLAY={os.environ.get('DISPLAY', ':0')}",
        f"XAUTHORITY={os.environ.get('XAUTHORITY', '')}",
        f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR', '')}",
        f"DBUS_SESSION_BUS_ADDRESS={os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')}",
        f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', 'xcb')}",
        f"QT_LOGGING_RULES=qt.qpa.wayland=false",
        f"SUDO_USER={os.environ.get('USER', '')}",
        f"GRUB_REAL_USER={os.environ.get('USER', '')}",
    ]

    cmd = ["pkexec", "env"] + env_fwd + [sys.executable, os.path.abspath(__file__)]
    log.info("Elevating via pkexec…")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def _elevate_fallback():
    """
    Fallback chain: gksudo → kdesudo → xterm+sudo.
    Used when pkexec is unavailable.
    """
    script = os.path.abspath(__file__)
    display = os.environ.get("DISPLAY", ":0")

    for tool in ["gksudo", "kdesudo"]:
        if shutil.which(tool):
            log.info("Elevating via %s…", tool)
            result = subprocess.run([tool, "--", sys.executable, script])
            sys.exit(result.returncode)

    if shutil.which("xterm") and shutil.which("sudo"):
        log.info("Elevating via xterm+sudo…")
        result = subprocess.run([
            "xterm", "-display", display,
            "-e", f"sudo {sys.executable} {script}"
        ])
        sys.exit(result.returncode)

    log.error("No graphical sudo tool found (pkexec/gksudo/kdesudo/xterm).")
    return False


def main():
    _preserve_display_env()

    # Already root — just launch the GUI
    if os.getuid() == 0:
        log.info("Running as root. Starting GUI…")
        from grub_configurator.gui import run
        run()
        return

    # Not root — show the graphical privilege prompt and re-exec as root
    _elevate_via_pkexec()


if __name__ == "__main__":
    main()