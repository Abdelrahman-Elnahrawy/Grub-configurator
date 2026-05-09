#!/usr/bin/env bash

set -euo pipefail

# ── Constants ─────────────────────────────────────────────────────

APPNAME="GRUB Configurator"
VERSION="1.0.0"

INSTALL_DIR="/opt/grub-configurator"
BIN_LINK="/usr/local/bin/grub-configurator"
DESKTOP_DIR="/usr/share/applications"

# Resolve script directory (critical for safe file copying)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors (portable-safe)
GREEN=$'\e[32m'
AMBER=$'\e[33m'
RED=$'\e[31m'
NC=$'\e[0m'

# Non-interactive package installs
export DEBIAN_FRONTEND=noninteractive
# ── Script Location Safety ────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prevent recursive self-copy
if [[ "$SCRIPT_DIR" == "$INSTALL_DIR" ]]; then
    echo -e "${RED}[ERROR]${NC} Do not run installer from inside $INSTALL_DIR"
    exit 1
fi

# ── Helper Functions ──────────────────────────────────────────────
info() {
    echo -e "${AMBER}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ── Root Check ────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Please run this installer with sudo or as root."
    exit 1
fi

# ── Dependency Installation ───────────────────────────────────────
install_python_deps() {
    info "Installing required dependencies..."

    if command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq
		apt-get install -y \
			python3 \
			python3-pip \
			python3-pyqt6 \
			grub-common \
			plymouth \
			plymouth-themes \
			plymouth-x11 \
			grub-emu

    elif command -v pacman >/dev/null 2>&1; then
	pacman -Sy --noconfirm \
		python \
		python-pip \
		python-pyqt6 \
		grub \
		plymouth \
		plymouth-x11 \
		grub-emu

    else
        error "Unsupported package manager."
        exit 1
    fi
}


# ── GRUB Reset Section ────────────────────────────────────────────
# ── GRUB Reset & Universal Recovery Section ────────────────────────
# A hardened, architecture-aware utility for GRUB restoration.
# ──────────────────────────────────────────────────────────────────
reset_grub_factory() {
    info "Initiating authoritative GRUB repair and factory reset..."

    # ── 1. Scoped Variable Initialization ──────────────────────────
    local OS_ID BOOTLOADER_ID="" EFI_TARGET ARCH
    
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
    else
        OS_ID="unknown"
    fi

    # ── 2. Remediation: Third-Party Conflicts ───────────────────────
    # Neutralize Grub Customizer proxies using safe 'find' operations.
    if [[ -d "/etc/grub.d/proxifiedScripts" ]] || [[ -f "/usr/bin/grub-customizer" ]]; then
        info "Remediating third-party script redirections..."
        
        # Safer than globbing: specifically target files with the proxy suffix
        find /etc/grub.d -maxdepth 1 -type f -name '*_proxy' -delete
        
        if [[ -d "/etc/grub.d/proxifiedScripts" ]]; then
            cp -af /etc/grub.d/proxifiedScripts/* /etc/grub.d/
            rm -rf /etc/grub.d/proxifiedScripts
        fi
        
        rm -rf /etc/grub.d/bin /etc/grub.d/backup || true
        success "Standard script architecture restored."
    fi

    # ── 3. Configuration Purge: /etc/default/grub ───────────────────
    if [[ -f "/etc/default/grub" ]]; then
        info "Purging custom variables and themes..."
        cp -f /etc/default/grub "/etc/default/grub.bak.$(date +%Y%m%d_%H%M%S)"
        
        sed -i '/^[[:space:]]*#\?GRUB_THEME=/d' /etc/default/grub
        sed -i '/^[[:space:]]*#\?GRUB_BACKGROUND=/d' /etc/default/grub
        sed -i '/^[[:space:]]*#\?GRUB_FONT=/d' /etc/default/grub
    fi

    # ── 4. Binary Restoration & Package Reinstall ──────────────────
    if command -v apt-get >/dev/null 2>&1; then
        info "Reinstalling core GRUB packages from repositories..."
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install --reinstall -y \
            -o Dpkg::Options::="--force-confmiss" \
            -o Dpkg::Options::="--force-confnew" \
            grub-common grub-pc-bin grub-efi-amd64-bin grub-efi-amd64-signed
            
    elif command -v pacman >/dev/null 2>&1; then
        info "Reinstalling GRUB via pacman..."
        pacman -Sy --noconfirm grub efibootmgr
    else
        error "Unsupported package manager. Manual repair required."
        return 1
    fi

    # ── 5. Triangulate Authoritative BOOTLOADER_ID ──────────────────
    # Layer 1: NVRAM Authority (Hardened Regex)
    if command -v efibootmgr >/dev/null 2>&1; then
        if efibootmgr | grep -Eiq '^Boot[0-9A-F]+\*?\s+ubuntu'; then BOOTLOADER_ID="ubuntu"
        elif efibootmgr | grep -Eiq '^Boot[0-9A-F]+\*?\s+debian'; then BOOTLOADER_ID="debian"
        elif efibootmgr | grep -Eiq '^Boot[0-9A-F]+\*?\s+fedora'; then BOOTLOADER_ID="fedora"
        fi
    fi

    # Layer 2: Filesystem Authority (Directory Check)
    if [[ -z "$BOOTLOADER_ID" ]]; then
        if [[ -d "/boot/efi/EFI/ubuntu" ]]; then BOOTLOADER_ID="ubuntu"
        elif [[ -d "/boot/efi/EFI/debian" ]]; then BOOTLOADER_ID="debian"
        elif [[ -d "/boot/efi/EFI/fedora" ]]; then BOOTLOADER_ID="fedora"
        fi
    fi

    # Layer 3: Metadata Fallback
    if [[ -z "$BOOTLOADER_ID" ]]; then
        case "$OS_ID" in
            ubuntu|pop|linuxmint|zorin) BOOTLOADER_ID="ubuntu" ;;
            debian)                    BOOTLOADER_ID="debian" ;;
            *)                         BOOTLOADER_ID="GRUB"   ;;
        esac
    fi
    info "Targeting Bootloader ID: $BOOTLOADER_ID"

    # ── 6. Hardware Synchronization (EFI Re-link) ───────────────────
    if [[ -d /sys/firmware/efi ]]; then
        if ! mountpoint -q /boot/efi; then
            error "EFI partition not detected at /boot/efi. Aborting hardware re-link."
            return 1
        fi

        # Architecture Auto-Detection
        ARCH="$(uname -m)"
        case "$ARCH" in
            x86_64)         EFI_TARGET="x86_64-efi" ;;
            aarch64|arm64)  EFI_TARGET="arm64-efi" ;;
            *)              EFI_TARGET="x86_64-efi" ;;
        esac

        info "Synchronizing $EFI_TARGET binaries with NVRAM..."
        if ! grub-install \
            --target="$EFI_TARGET" \
            --efi-directory=/boot/efi \
            --bootloader-id="$BOOTLOADER_ID" \
            --recheck; then
            error "grub-install failed. Hardware sync incomplete."
            return 1
        fi
    else
        info "Legacy BIOS detected. Hardware re-link skipped."
    fi

    # ── 7. Rebuild Configuration & Initramfs ────────────────────────
    # NEW: Force Console Mode and Visibility Patcher
    if [[ -f "/etc/default/grub" ]]; then
        info "Patching /etc/default/grub for high-compatibility Console mode..."
        
        # Ensure the console line is uncommented and set correctly
        # This handles cases where it's missing, commented, or set to something else
        if grep -q "^#\?GRUB_TERMINAL=" /etc/default/grub; then
            sed -i 's/^#\?GRUB_TERMINAL=.*/GRUB_TERMINAL="console"/' /etc/default/grub
        else
            echo 'GRUB_TERMINAL="console"' >> /etc/default/grub
        fi

        # Force the menu style and a longer timeout for visibility
        sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE="menu"/' /etc/default/grub
        sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT="10"/' /etc/default/grub
        
        # Ensure OS Prober is enabled to catch Windows
        if grep -q "^GRUB_DISABLE_OS_PROBER=" /etc/default/grub; then
            sed -i 's/^GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER="false"/' /etc/default/grub
        else
            echo 'GRUB_DISABLE_OS_PROBER="false"' >> /etc/default/grub
        fi
    fi

    info "Regenerating boot configuration..."
    if command -v update-grub >/dev/null 2>&1; then
        update-grub
    else
        grub-mkconfig -o /boot/grub/grub.cfg
    fi

    info "Updating initramfs image..."
    if command -v update-initramfs >/dev/null 2>&1; then
        update-initramfs -u
    elif command -v mkinitcpio >/dev/null 2>&1; then
        mkinitcpio -P
    elif command -v dracut >/dev/null 2>&1; then
        dracut --force
    fi

    # ── 8. Final Verification ───────────────────────────────────────
    success "GRUB reset and Console repair complete!"
    if command -v efibootmgr >/dev/null 2>&1 && [[ -d /sys/firmware/efi ]]; then
        info "Verified Boot Order:"
        efibootmgr | grep -i "BootOrder" || true
        efibootmgr | grep -Eiq "^Boot[0-9A-F]+\*?\s+$BOOTLOADER_ID" && \
            info "Confirmed: $BOOTLOADER_ID is registered in NVRAM."
    fi
}
# ── Application Installation ──────────────────────────────────────
install_app() {

    echo -e "${GREEN}Installing GRUB Configurator (universal mode)...${NC}"

    local BIN_LINK="/usr/local/bin/grub-configurator"
    local DESKTOP_FILE="grub-configurator.desktop"
    local ICON_FILE="grub-configurator.png"

    # ── Validate source ───────────────────────────────
    [[ -f "$SCRIPT_DIR/main.py" ]] || {
        echo -e "${RED}main.py not found in $SCRIPT_DIR${NC}"
        exit 1
    }

    # ── Core install (ALWAYS works) ───────────────────
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"

    cp -a "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/main.py"

    # ── Universal launcher ────────────────────────────
    # pkexec in main.py handles the graphical privilege prompt.
    # The launcher just needs to forward display vars in case they're missing.
    cat > "$BIN_LINK" <<'LAUNCHEREOF'
#!/usr/bin/env bash
# grub-configurator launcher
export DISPLAY="${DISPLAY:-:0}"
if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi
exec python3 /opt/grub-configurator/main.py "$@"
LAUNCHEREOF
    chmod +x "$BIN_LINK"

    # ── Optional: Desktop integration ─────────────────
    if [[ -d "$DESKTOP_DIR" && -f "$SCRIPT_DIR/$DESKTOP_FILE" ]]; then
        cp "$SCRIPT_DIR/$DESKTOP_FILE" "$DESKTOP_DIR/"
        chmod 644 "$DESKTOP_DIR/$DESKTOP_FILE"

        command -v update-desktop-database >/dev/null 2>&1 && \
            update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    fi

    # ── Optional: Icon ────────────────────────────────
    if [[ -f "$SCRIPT_DIR/$ICON_FILE" ]] && [[ -d /usr/share/icons ]]; then
        local ICON_DEST="/usr/share/icons/hicolor/256x256/apps"
        mkdir -p "$ICON_DEST"
        cp "$SCRIPT_DIR/$ICON_FILE" "$ICON_DEST/grub-configurator.png"
        chmod 644 "$ICON_DEST/grub-configurator.png"

        command -v gtk-update-icon-cache >/dev/null 2>&1 && \
            gtk-update-icon-cache /usr/share/icons/hicolor >/dev/null 2>&1 || true
    fi

    # ── Polkit policy ─────────────────────────────────────────────────
    local POLICY_SRC="$SCRIPT_DIR/com.github.grub-configurator.policy"
    local POLICY_DEST="/usr/share/polkit-1/actions/com.github.grub-configurator.policy"
    if [[ -f "$POLICY_SRC" ]]; then
        cp "$POLICY_SRC" "$POLICY_DEST"
        chmod 644 "$POLICY_DEST"
        success "Polkit policy installed."
    else
        error "Policy file not found: $POLICY_SRC"
    fi

    # ── Sudoers drop-in: preserve display env vars ───────────────────
    # Makes "sudo grub-configurator" work by telling sudo NOT to strip
    # the X11/Wayland display environment variables.
    local SUDOERS_DROP="/etc/sudoers.d/grub-configurator"
    cat > "$SUDOERS_DROP" <<'SUDOEOF'
# Allow grub-configurator to keep display vars when run with sudo.
# Generated by grub-configurator installer. Safe to delete on uninstall.
Defaults env_keep += "DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS WAYLAND_DISPLAY"
SUDOEOF
    chmod 440 "$SUDOERS_DROP"
    success "Sudoers drop-in installed (display vars preserved under sudo)."

    echo -e "${GREEN}Installed successfully nyaw.${NC}"
    echo -e "Run with: ${AMBER}grub-configurator${NC}"
    echo -e "${AMBER}[TIP]${NC} Run WITHOUT sudo — privilege prompts happen automatically inside the app."
}

# ── Uninstall Section ─────────────────────────────────────────────
uninstall_app() {

    info "Removing $APPNAME..."

    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        success "Removed installation directory."
    fi

    if [[ -L "$BIN_LINK" || -f "$BIN_LINK" ]]; then
        rm -f "$BIN_LINK"
        success "Removed launcher."
    fi

    if [[ -f "$DESKTOP_DIR/grub-configurator.desktop" ]]; then

        rm -f "$DESKTOP_DIR/grub-configurator.desktop"

        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
        fi

        success "Removed desktop shortcut."
    fi

    if [[ -f "/etc/sudoers.d/grub-configurator" ]]; then
        rm -f "/etc/sudoers.d/grub-configurator"
        success "Removed sudoers drop-in."
    fi

    if [[ -f "/usr/share/polkit-1/actions/com.github.grub-configurator.policy" ]]; then
        rm -f "/usr/share/polkit-1/actions/com.github.grub-configurator.policy"
        success "Removed polkit policy."
    fi

    echo ""
    success "Uninstallation complete."
    info "System dependencies were intentionally kept."

    exit 0
}

# ── Main ──────────────────────────────────────────────────────────

case "${1:-}" in

    --uninstall)
        uninstall_app
        ;;

    "")
        ;;

    *)
        error "Unknown option: $1"
        echo ""
        echo "Usage:"
        echo "  sudo ./install.sh"
        echo "  sudo ./install.sh --uninstall"
        exit 1
        ;;
esac

clear 2>/dev/null || true

echo -e "${GREEN}"
echo "  ██████╗ ██████╗ ██╗   ██╗██████╗"
echo "  ██╔════╝ ██╔══██╗██║   ██║██╔══██╗"
echo "  ██║  ███╗██████╔╝██║   ██║██████╔╝"
echo "  ██║   ██║██╔══██╗██║   ██║██╔══██╗"
echo "  ╚██████╔╝██║  ██║╚██████╔╝██████╔╝"
echo "   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═════╝"
echo -e "  CONFIGURATOR  —  Universal Installer${NC}\n"

# Optional GRUB reset
read -r -p "Reset GRUB to factory defaults before installing? (y/N): " want_reset

if [[ "$want_reset" =~ ^[Yy]$ ]]; then
    reset_grub_factory
fi

# Install dependencies
install_python_deps

# Install application
install_app

echo ""
success "Installed successfully!"

echo -e "  Run it:      ${AMBER}grub-configurator${NC}"
echo -e "  Uninstall:   ${AMBER}sudo ./install.sh --uninstall${NC}"