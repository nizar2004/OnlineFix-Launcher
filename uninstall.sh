#!/usr/bin/env bash
#
# OnlineFix Launcher — uninstaller
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nizar2004/OnlineFix-Launcher/main/uninstall.sh | bash
#   ./uninstall.sh --purge      # also delete config, covers, logs and games data
#   ./uninstall.sh --yes        # do not ask for confirmation
#
# Options:
#   --purge     Remove configuration and data as well
#   --system    Also remove a system-wide installation
#   --yes       Assume "yes" for all prompts
#   --help      Show this help

set -euo pipefail

APP_NAME="OnlineFix Launcher"
APP_SLUG="onlinefix-launcher"
APP_ID="io.github.nizar2004.OnlineFixLauncher"

PURGE=0
SYSTEM=0
ASSUME_YES=0

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'

info()  { printf '%s==>%s %s\n' "$GREEN" "$RESET" "$*"; }
warn()  { printf '%s[warning]%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
error() { printf '%s[error]%s %s\n' "$RED" "$RESET" "$*" >&2; }

usage() {
    sed -n '3,16p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge)   PURGE=1 ;;
        --system)  SYSTEM=1 ;;
        -y|--yes)  ASSUME_YES=1 ;;
        -h|--help) usage ;;
        *) error "Unknown option: $1"; usage ;;
    esac
    shift
done

confirm() {
    [[ "$ASSUME_YES" == "1" ]] && return 0
    local reply
    read -r -p "$1 [y/N] " reply || true
    [[ "$reply" =~ ^[Yy]$ ]]
}

remove_path() {
    local path="$1" desc="$2"
    if [[ -e "$path" ]]; then
        rm -rf "$path"
        info "Removed $desc: $path"
    else
        printf '%s      skipped%s %s (not found)\n' "$DIM" "$RESET" "$path"
    fi
}

stop_running() {
    if pgrep -f "onlinefix-launcher/main.py" >/dev/null 2>&1; then
        warn "The launcher is still running — stopping it."
        pkill -f "onlinefix-launcher/main.py" >/dev/null 2>&1 || true
        sleep 1
    fi
}

remove_user_install() {
    remove_path "$HOME/.local/share/$APP_SLUG" "application"
    remove_path "$HOME/.local/bin/$APP_SLUG" "command"
    remove_path "$HOME/.local/share/applications/$APP_ID.desktop" "desktop entry"
    remove_path "$HOME/.local/share/icons/hicolor/512x512/apps/$APP_ID.png" "icon"
    remove_path "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg" "icon"
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
}

remove_system_install() {
    local SUDO=""
    if [[ $EUID -ne 0 ]]; then
        if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else
            warn "Need root to remove the system-wide installation — skipping."
            return 0
        fi
    fi
    $SUDO rm -rf "/usr/local/share/$APP_SLUG" && info "Removed application: /usr/local/share/$APP_SLUG"
    $SUDO rm -f  "/usr/local/bin/$APP_SLUG" && info "Removed command: /usr/local/bin/$APP_SLUG"
    $SUDO rm -f  "/usr/share/applications/$APP_ID.desktop" && info "Removed desktop entry"
    $SUDO rm -f  "/usr/share/icons/hicolor/512x512/apps/$APP_ID.png" || true
    $SUDO rm -f  "/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg" || true
    $SUDO update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
    $SUDO gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
}

remove_data() {
    remove_path "$HOME/.config/OnlineFixLauncher" "configuration"
    remove_path "$HOME/.cache/OnlineFixLauncher" "cache"
    remove_path "$HOME/.local/state/OnlineFixLauncher" "state and logs"
    remove_path "$HOME/.local/share/OnlineFixLauncher" "games, downloads and covers"
    # Desktop shortcuts created by the launcher for individual games
    if compgen -G "$HOME/Desktop/*.desktop" >/dev/null 2>&1; then
        local f
        for f in "$HOME/Desktop"/*.desktop; do
            if grep -q "$APP_ID" "$f" 2>/dev/null; then
                rm -f "$f"
                info "Removed game shortcut: $f"
            fi
        done
    fi
}

main() {
    printf '%s%s uninstaller%s\n' "$BOLD" "$APP_NAME" "$RESET"
    echo

    stop_running

    if ! confirm "Remove $APP_NAME?"; then
        info "Nothing was removed."
        exit 0
    fi

    remove_user_install

    if [[ "$SYSTEM" == "1" ]]; then
        remove_system_install
    fi

    if [[ "$PURGE" == "1" ]]; then
        echo
        info "Removing configuration and data…"
        remove_data
    fi

    echo
    printf '%s%s removed.%s\n' "$BOLD" "$APP_NAME" "$RESET"
    if [[ "$PURGE" != "1" ]]; then
        hint "Your configuration was kept. Use --purge to delete it as well."
    fi
}

main
