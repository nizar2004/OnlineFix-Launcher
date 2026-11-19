#!/usr/bin/env bash
#
# OnlineFix Launcher — installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nizar2004/OnlineFix-Launcher/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/nizar2004/OnlineFix-Launcher/main/install.sh | bash -s -- --system
#   ./install.sh --help
#
# Options:
#   --user        Install for the current user (default)
#   --system      Install system-wide (requires sudo)
#   --no-deps     Do not install system packages
#   --uninstall   Remove the launcher (same as uninstall.sh)
#   --help        Show this help

set -euo pipefail

APP_NAME="OnlineFix Launcher"
APP_SLUG="onlinefix-launcher"
APP_ID="io.github.nizar2004.OnlineFixLauncher"
REPO="nizar2004/OnlineFix-Launcher"
REPO_NAME="OnlineFix-Launcher"
BRANCH="main"

MODE="user"
INSTALL_DEPS=1
DO_UNINSTALL=0

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'

info()  { printf '%s==>%s %s\n' "$GREEN" "$RESET" "$*"; }
warn()  { printf '%s[warning]%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
error() { printf '%s[error]%s %s\n' "$RED" "$RESET" "$*" >&2; }
hint()  { printf '%s[hint]%s %s\n' "$DIM" "$RESET" "$*"; }

usage() {
    sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)      MODE="user" ;;
        --system)    MODE="system" ;;
        --no-deps)   INSTALL_DEPS=0 ;;
        --uninstall) DO_UNINSTALL=1 ;;
        -h|--help)   usage ;;
        *) error "Unknown option: $1"; usage ;;
    esac
    shift
done

# --------------------------------------------------------------------------
# Uninstall shortcut
# --------------------------------------------------------------------------
if [[ "$DO_UNINSTALL" == "1" ]]; then
    UNINSTALL_URL="https://raw.githubusercontent.com/$REPO/$BRANCH/uninstall.sh"
    if curl -fsSL "$UNINSTALL_URL" -o /tmp/ofl-uninstall.sh 2>/dev/null; then
        bash /tmp/ofl-uninstall.sh --yes ${MODE:+$([ "$MODE" = "system" ] && echo --system)}
        rm -f /tmp/ofl-uninstall.sh
    else
        error "Could not download uninstall.sh"
        exit 1
    fi
    exit 0
fi

# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------
PKG_MANAGER="none"
if command -v apt-get >/dev/null 2>&1; then      PKG_MANAGER="apt"
elif command -v dnf >/dev/null 2>&1; then         PKG_MANAGER="dnf"
elif command -v pacman >/dev/null 2>&1; then      PKG_MANAGER="pacman"
elif command -v zypper >/dev/null 2>&1; then      PKG_MANAGER="zypper"
elif command -v apk >/dev/null 2>&1; then         PKG_MANAGER="apk"
fi

SUDO=""
if [[ "$MODE" == "system" ]]; then
    if [[ $EUID -ne 0 ]]; then
        if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else
            error "System-wide install needs root. Re-run with sudo, or use --user."
            exit 1
        fi
    fi
fi

install_deps() {
    [[ "$INSTALL_DEPS" == "1" ]] || { hint "Skipping dependency installation (--no-deps)"; return 0; }

    if [[ "$PKG_MANAGER" == "none" ]]; then
        warn "Unsupported package manager — install the dependencies manually:"
        printf '    %s\n' "python3 · python3-gobject/PyGObject · GTK 4 · libadwaita · WebKitGTK 6.0"
        return 0
    fi

    local -a required optional
    case "$PKG_MANAGER" in
        apt)
            required=(python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libwebkit2gtk-6.0-4)
            optional=(p7zip-full unrar-free)
            ;;
        pacman)
            required=(python-gobject gtk4 libadwaita webkit2gtk-6.0)
            optional=(p7zip unrar)
            ;;
        dnf)
            required=(python3-gobject gtk4 libadwaita webkit2gtk6.0)
            optional=(p7zip unrar)
            ;;
        zypper)
            required=(python3-gobject gtk4 libadwaita webkit2gtk-6.0)
            optional=(p7zip unrar)
            ;;
        apk)
            required=(py3-gobject py3-gi gtk4 libadwaita webkit2gtk-6.0)
            optional=(p7zip unrar)
            ;;
    esac

    info "Installing system dependencies ($PKG_MANAGER)…"
    local sudo_cmd=""
    if [[ "$PKG_MANAGER" != "none" && $EUID -ne 0 ]]; then
        if command -v sudo >/dev/null 2>&1; then sudo_cmd="sudo"
        else warn "Need root to install packages — try again with sudo."; return 0; fi
    fi

    case "$PKG_MANAGER" in
        apt)
            $sudo_cmd apt-get update -qq || true
            $sudo_cmd apt-get install -y --no-install-recommends "${required[@]}" || \
                error "Failed to install dependencies"
            # Optional archive tools
            $sudo_cmd apt-get install -y --no-install-recommends "${optional[@]}" >/dev/null 2>&1 || true
            ;;
        pacman)
            $sudo_cmd pacman -S --needed --noconfirm "${required[@]}" || error "Failed to install dependencies"
            $sudo_cmd pacman -S --needed --noconfirm "${optional[@]}" >/dev/null 2>&1 || true
            ;;
        dnf)
            $sudo_cmd dnf install -y "${required[@]}" || error "Failed to install dependencies"
            $sudo_cmd dnf install -y "${optional[@]}" >/dev/null 2>&1 || true
            ;;
        zypper)
            $sudo_cmd zypper --non-interactive install "${required[@]}" || error "Failed to install dependencies"
            $sudo_cmd zypper --non-interactive install "${optional[@]}" >/dev/null 2>&1 || true
            ;;
        apk)
            $sudo_cmd apk add "${required[@]}" || error "Failed to install dependencies"
            $sudo_cmd apk add "${optional[@]}" >/dev/null 2>&1 || true
            ;;
    esac
    info "Dependencies installed."
}

check_runtime() {
    local missing=0
    command -v python3 >/dev/null 2>&1 || { error "python3 is required"; missing=1; }
    python3 - <<'PY' >/dev/null 2>&1 || { echo "  missing: python3-gobject (PyGObject)"; }
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
PY
    if [[ $missing -eq 1 ]]; then
        error "Required runtime missing. Install python3 + python3-gobject and try again."
        exit 1
    fi
    if ! python3 -c "import gi; gi.require_version('WebKit','6.0'); from gi.repository import WebKit" >/dev/null 2>&1; then
        warn "WebKitGTK 6.0 was not found — the built-in browser will not work."
        hint "Install it with: webkit2gtk-6.0 (Arch) / libwebkit2gtk-6.0-4 (Debian) / webkit2gtk6.0 (Fedora)"
    fi
}

# --------------------------------------------------------------------------
# Source
# --------------------------------------------------------------------------
TMP_DIR=""
cleanup() { [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]] && rm -rf "$TMP_DIR"; }
trap cleanup EXIT

acquire_source() {
    local self="${BASH_SOURCE[0]}"
    if [[ -f "$self" ]]; then
        local dir; dir="$(cd "$(dirname "$self")" && pwd)"
        if [[ -d "$dir/oflauncher" ]]; then
            SRC_DIR="$dir"
            info "Using local source: $SRC_DIR"
            return 0
        fi
    fi

    info "Downloading $APP_NAME…"
    TMP_DIR="$(mktemp -d)"
    local tarball="$TMP_DIR/source.tar.gz"
    if ! curl -fL --retry 3 -o "$tarball" "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz"; then
        error "Download failed. Check your internet connection."
        exit 1
    fi
    tar -xzf "$tarball" -C "$TMP_DIR"
    # The archive contains a single top-level folder — find the one that holds
    # the application, regardless of how GitHub names it.
    SRC_DIR=""
    for candidate in "$TMP_DIR"/*/; do
        if [[ -d "$candidate/oflauncher" ]]; then
            SRC_DIR="${candidate%/}"
            break
        fi
    done
    if [[ -z "$SRC_DIR" ]]; then
        error "Could not unpack the downloaded archive."
        exit 1
    fi
}

# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------
install_launcher() {
    if [[ "$MODE" == "system" ]]; then
        APP_DIR="/usr/local/share/$APP_SLUG"
        BIN_DIR="/usr/local/bin"
        DATA_DIR="/usr/share"
        DESKTOP_DIR="$DATA_DIR/applications"
        ICON_DIR="$DATA_DIR/icons/hicolor"
        RUN_AS="$SUDO"
    else
        APP_DIR="$HOME/.local/share/$APP_SLUG"
        BIN_DIR="$HOME/.local/bin"
        DATA_DIR="$HOME/.local/share"
        DESKTOP_DIR="$DATA_DIR/applications"
        ICON_DIR="$DATA_DIR/icons/hicolor"
        RUN_AS=""
    fi

    info "Installing to $APP_DIR"
    if [[ -n "$RUN_AS" ]]; then
        $RUN_AS mkdir -p "$APP_DIR" "$BIN_DIR"
        $RUN_AS rm -rf "$APP_DIR/oflauncher" "$APP_DIR/data"
        $RUN_AS cp -r "$SRC_DIR/oflauncher" "$APP_DIR/"
        $RUN_AS cp -r "$SRC_DIR/data" "$APP_DIR/"
        $RUN_AS cp "$SRC_DIR/main.py" "$APP_DIR/main.py"
        $RUN_AS cp "$SRC_DIR/LICENSE" "$APP_DIR/LICENSE" 2>/dev/null || true
        $RUN_AS cp "$SRC_DIR/README.md" "$APP_DIR/README.md" 2>/dev/null || true
    else
        mkdir -p "$APP_DIR" "$BIN_DIR"
        rm -rf "$APP_DIR/oflauncher" "$APP_DIR/data"
        cp -r "$SRC_DIR/oflauncher" "$APP_DIR/"
        cp -r "$SRC_DIR/data" "$APP_DIR/"
        cp "$SRC_DIR/main.py" "$APP_DIR/main.py"
        cp "$SRC_DIR/LICENSE" "$APP_DIR/LICENSE" 2>/dev/null || true
        cp "$SRC_DIR/README.md" "$APP_DIR/README.md" 2>/dev/null || true
    fi
    find "$APP_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

    # launcher entry point
    local launcher="$BIN_DIR/$APP_SLUG"
    local launch_cmd="#!/usr/bin/env bash
# $APP_NAME launcher
exec python3 \"$APP_DIR/main.py\" \"\$@\"
"
    if [[ -n "$RUN_AS" ]]; then
        printf '%s' "$launch_cmd" | $RUN_AS tee "$launcher" >/dev/null
        $RUN_AS chmod +x "$launcher"
    else
        printf '%s' "$launch_cmd" > "$launcher"
        chmod +x "$launcher"
    fi

    # desktop entry
    local desktop_file="$DESKTOP_DIR/$APP_ID.desktop"
    local desktop_content="[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Game Launcher
Comment=Play your own games with multiplayer fixes on Linux
Exec=$launcher
Icon=$APP_ID
Terminal=false
StartupNotify=true
Categories=Game;Utility;
Keywords=game;games;launcher;proton;wine;onlinefix;multiplayer;
"
    if [[ -n "$RUN_AS" ]]; then
        $RUN_AS mkdir -p "$DESKTOP_DIR"
        printf '%s' "$desktop_content" | $RUN_AS tee "$desktop_file" >/dev/null
        $RUN_AS chmod +x "$desktop_file"
        $RUN_AS mkdir -p "$ICON_DIR/512x512/apps" "$ICON_DIR/scalable/apps"
        $RUN_AS cp "$SRC_DIR/data/icon.png" "$ICON_DIR/512x512/apps/$APP_ID.png"
        $RUN_AS cp "$SRC_DIR/data/icon.svg" "$ICON_DIR/scalable/apps/$APP_ID.svg"
        $RUN_AS update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
        $RUN_AS gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true
    else
        mkdir -p "$DESKTOP_DIR" "$ICON_DIR/512x512/apps" "$ICON_DIR/scalable/apps"
        printf '%s' "$desktop_content" > "$desktop_file"
        chmod +x "$desktop_file"
        cp "$SRC_DIR/data/icon.png" "$ICON_DIR/512x512/apps/$APP_ID.png"
        cp "$SRC_DIR/data/icon.svg" "$ICON_DIR/scalable/apps/$APP_ID.svg"
        command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
        command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true
    fi
}

post_install() {
    echo
    printf '%s%s installed successfully!%s\n' "$BOLD" "$APP_NAME" "$RESET"
    if [[ "$MODE" == "system" ]]; then
        printf '  Run it with:  %s%s%s\n' "$BOLD" "$launcher" "$RESET"
    else
        printf '  Run it with:  %s%s%s\n' "$BOLD" "$APP_SLUG" "$RESET"
        if ! echo ":$PATH:" | grep -q ":$HOME/.local/bin:"; then
            hint "Add $HOME/.local/bin to your PATH:"
            printf '    export PATH=\"$HOME/.local/bin:\$PATH\"\n'
        fi
    fi
    echo
    printf '  %sTip:%s add "%s" to your applications menu, or run\n' "$DIM" "$RESET" "$APP_NAME"
    printf '    %s%s --launch \"Game name\"%s   to start a game directly\n' "$DIM" "$APP_SLUG" "$RESET"
    printf '    %s%s --kill%s                  to stop a running game\n' "$DIM" "$APP_SLUG" "$RESET"
    echo
}

main() {
    printf '%s%s installer%s\n' "$BOLD" "$APP_NAME" "$RESET"
    echo

    install_deps
    check_runtime
    acquire_source
    install_launcher
    post_install
}

main
