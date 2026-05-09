#!/usr/bin/env python3
"""
grub_preview.py — standalone GRUB theme previewer
Finds grub2-theme-preview (including in ~/.local/bin of the real user)
and launches it for any theme directory you point it at.
"""

import os
import sys
import subprocess
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path


# ── Tool discovery ────────────────────────────────────────────────────────────

def find_preview_tool() -> str | None:
    # grub2-theme-preview must be checked before grub-emu —
    # grub-emu is a shell emulator, not a visual previewer.
    names = ("grub2-theme-preview",)   # only the real preview tool

    real_user = os.environ.get("SUDO_USER") or os.environ.get("USER") or ""

    # Check real user's ~/.local/bin FIRST (pipx installs here)
    candidate_dirs = []
    if real_user:
        candidate_dirs.append(f"/home/{real_user}/.local/bin")
    candidate_dirs += [
        os.path.expanduser("~/.local/bin"),
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]

    for d in candidate_dirs:
        full = os.path.join(d, "grub2-theme-preview")
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full

    # shutil.which as last resort
    return shutil.which("grub2-theme-preview")
def run_preview(theme_dir: str, tool: str) -> tuple[bool, str]:
    try:
        if "theme-preview" in tool:
            cmd = [tool, theme_dir]
        else:
            # grub-emu: no -c flag, no -r flag — just pass the module dir
            module_dir = next(
                (p for p in (
                    "/boot/grub/x86_64-efi",
                    "/boot/grub/i386-pc",
                    "/usr/lib/grub/x86_64-efi",
                    "/usr/lib/grub/i386-pc",
                ) if os.path.isdir(p)),
                None
            )
            if not module_dir:
                return False, "GRUB module directory not found."
            cmd = [tool, "-d", module_dir]

        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        _, stderr = proc.communicate()
        err = stderr.decode(errors="replace").strip()
        if proc.returncode != 0 and err:
            return False, err
        return True, "Preview closed."
    except Exception as e:
        return False, str(e)

# ── GUI ───────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    BG      = "#0f0f14"
    SURFACE = "#1a1a24"
    BORDER  = "#2a2a3a"
    ACCENT  = "#7c6af7"
    ACCENT2 = "#4ecdc4"
    FG      = "#e8e6f0"
    FG_DIM  = "#6b6880"
    FONT_H  = ("JetBrains Mono", 13, "bold")
    FONT_B  = ("JetBrains Mono", 11)
    FONT_S  = ("JetBrains Mono", 9)

    def __init__(self):
        super().__init__()
        self.title("GRUB Theme Preview")
        self.configure(bg=self.BG)
        self.resizable(False, False)
        self._build()
        self._check_tool()

    def _build(self):
        # ── header
        hdr = tk.Frame(self, bg=self.BG, pady=20)
        hdr.pack(fill="x", padx=24)

        tk.Label(hdr, text="⬡", font=("JetBrains Mono", 28),
                 fg=self.ACCENT, bg=self.BG).pack(side="left", padx=(0, 12))

        titles = tk.Frame(hdr, bg=self.BG)
        titles.pack(side="left")
        tk.Label(titles, text="GRUB PREVIEW", font=("JetBrains Mono", 16, "bold"),
                 fg=self.FG, bg=self.BG).pack(anchor="w")
        tk.Label(titles, text="standalone theme launcher", font=self.FONT_S,
                 fg=self.FG_DIM, bg=self.BG).pack(anchor="w")

        # ── divider
        tk.Frame(self, bg=self.BORDER, height=1).pack(fill="x", padx=24)

        # ── tool status
        self.tool_frame = tk.Frame(self, bg=self.SURFACE,
                                   highlightbackground=self.BORDER,
                                   highlightthickness=1)
        self.tool_frame.pack(fill="x", padx=24, pady=(16, 0))
        self.tool_label = tk.Label(self.tool_frame, text="Detecting tool…",
                                   font=self.FONT_S, fg=self.FG_DIM,
                                   bg=self.SURFACE, anchor="w", pady=8, padx=12)
        self.tool_label.pack(fill="x")

        # ── theme dir picker
        pick_frame = tk.Frame(self, bg=self.BG)
        pick_frame.pack(fill="x", padx=24, pady=16)

        tk.Label(pick_frame, text="THEME DIRECTORY",
                 font=("JetBrains Mono", 9, "bold"),
                 fg=self.ACCENT2, bg=self.BG).pack(anchor="w", pady=(0, 6))

        row = tk.Frame(pick_frame, bg=self.BG)
        row.pack(fill="x")

        self.path_var = tk.StringVar(value="")
        entry = tk.Entry(row, textvariable=self.path_var,
                         font=self.FONT_B, fg=self.FG, bg=self.SURFACE,
                         insertbackground=self.ACCENT,
                         relief="flat", bd=0,
                         highlightbackground=self.BORDER,
                         highlightcolor=self.ACCENT,
                         highlightthickness=1)
        entry.pack(side="left", fill="x", expand=True,
                   ipady=8, ipadx=10, padx=(0, 8))

        btn_browse = tk.Button(row, text="Browse",
                               font=self.FONT_S, fg=self.FG,
                               bg=self.BORDER, activebackground=self.ACCENT,
                               activeforeground="#fff",
                               relief="flat", bd=0, cursor="hand2",
                               padx=14, pady=8,
                               command=self._browse)
        btn_browse.pack(side="left")

        # quick-fill known path
        default = "/boot/grub/themes"
        if os.path.isdir(default):
            subdirs = [d for d in Path(default).iterdir() if d.is_dir()]
            if subdirs:
                self.path_var.set(str(subdirs[0]))

        # ── launch button
        self.btn_launch = tk.Button(self, text="▶  Launch Preview",
                                    font=("JetBrains Mono", 12, "bold"),
                                    fg="#fff", bg=self.ACCENT,
                                    activebackground="#9d8fff",
                                    activeforeground="#fff",
                                    relief="flat", bd=0, cursor="hand2",
                                    pady=12,
                                    command=self._launch)
        self.btn_launch.pack(fill="x", padx=24, pady=(0, 8))

        # ── status bar
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self.status_var,
                 font=self.FONT_S, fg=self.FG_DIM, bg=self.BG,
                 anchor="w").pack(fill="x", padx=26, pady=(0, 16))

    def _check_tool(self):
        self.tool = find_preview_tool()
        if self.tool:
            name = Path(self.tool).name
            self.tool_label.config(
                text=f"✓  {name}   ({self.tool})",
                fg=self.ACCENT2
            )
        else:
            self.tool_label.config(
                text="✗  No preview tool found — run:  pipx install grub2-theme-preview",
                fg="#e05c6e"
            )
            self.btn_launch.config(state="disabled", bg=self.BORDER)

    def _browse(self):
        d = filedialog.askdirectory(title="Select GRUB theme directory",
                                    initialdir="/boot/grub/themes")
        if d:
            self.path_var.set(d)

    def _launch(self):
        theme = self.path_var.get().strip()
        if not theme or not os.path.isdir(theme):
            messagebox.showerror("Invalid path", "Please select a valid theme directory.")
            return
        if not self.tool:
            messagebox.showerror("No tool", "Preview tool not found.")
            return

        self.status_var.set("Launching preview…")
        self.update()

        ok, msg = run_preview(theme, self.tool)
        self.status_var.set(msg if ok else f"Error: {msg}")
        if not ok:
            messagebox.showerror("Preview failed", msg)


if __name__ == "__main__":
    # If a path was passed as CLI arg, skip the GUI
    if len(sys.argv) == 2 and os.path.isdir(sys.argv[1]):
        tool = find_preview_tool()
        if not tool:
            print("No preview tool found. Run: pipx install grub2-theme-preview")
            sys.exit(1)
        ok, msg = run_preview(sys.argv[1], tool)
        print(msg)
        sys.exit(0 if ok else 1)

    App().mainloop()
