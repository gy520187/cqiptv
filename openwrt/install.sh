#!/bin/sh
# cqiptv OpenWrt 一键安装/更新/卸载脚本（可互动）
# 适用: OpenWrt 24.10 x86_64 / iStoreOS x86_64
#
# 用法:
#   sh install.sh               交互模式（菜单选择，推荐）
#   sh install.sh install      安装
#   sh install.sh update       更新到最新版
#   sh install.sh reinstall    强制重装
#   sh install.sh uninstall    卸载
#   sh install.sh status       查看状态
#   sh install.sh help          帮助
#
# 环境变量:
#   GITHUB_MIRROR=official|gh-proxy|ghfast   指定 GitHub 访问方式（非交互模式）

set -u

# ---------- GitHub 仓库与下载地址 ----------
REPO_OWNER="gy520187"
REPO_NAME="cqiptv"
RELEASE_VERSION="v1.0.0"
PKG_MAIN="cqiptv_1.0.0-1_x86_64.ipk"
PKG_LUCI="luci-app-cqiptv_1.0.0-1_x86_64.ipk"
ARCH="x86_64"

BASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
TMPDIR="/tmp/cqiptv-install-$$"

# ---------- 颜色输出 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC} %s\n" "$*"; }
err()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }

ACTION="${1:-}"

# ---------- 平台环境检测 ----------
check_env() {
    # 是否 OpenWrt / iStoreOS（存在 opkg）
    if [ ! -x /bin/opkg ]; then
        err "未检测到 opkg，本脚本仅适用于 OpenWrt / iStoreOS。"
        exit 1
    fi
    # 架构检测
    if ! opkg print-architecture 2>/dev/null | grep -q "$ARCH"; then
        err "当前架构不受支持（需要 $ARCH，当前: $(uname -m)）。"
        exit 1
    fi
    # curl 检测，缺失则自动安装
    if ! command -v curl >/dev/null 2>&1; then
        info "未检测到 curl，正在安装..."
        opkg update >/dev/null 2>&1 || { err "opkg update 失败"; exit 1; }
        opkg install curl >/dev/null 2>&1 || { err "安装 curl 失败"; exit 1; }
    fi
    # GitHub Release 可达性
    if ! curl -kLs --max-time 10 -o /dev/null -w '%{http_code}' "$BASE_URL/$PKG_MAIN" 2>/dev/null | grep -q '200'; then
        err "无法访问下载地址（$BASE_URL），请检查网络或在交互模式中选择镜像。"
        exit 1
    fi
}

# ---------- 选择 GitHub 访问方式（交互模式） ----------
select_github_mirror() {
    echo ""
    echo "=========================================="
    echo " 选择 GitHub 访问方式"
    echo "=========================================="
    echo ""
    echo "  1) GitHub 官方 (直连)"
    echo "  2) gh-proxy.com (镜像加速)"
    echo "  3) ghfast.top (镜像加速)"
    echo ""
    printf "请输入选项 [1-3] (默认: 1): "
    read choice < /dev/tty || choice="1"
    [ -z "$choice" ] && choice="1"
    echo ""
    case "$choice" in
        1)
            BASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
            info "使用 GitHub 官方直连"
            ;;
        2)
            BASE_URL="https://gh-proxy.com/https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
            info "使用 gh-proxy.com 镜像加速"
            ;;
        3)
            BASE_URL="https://ghfast.top/https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
            info "使用 ghfast.top 镜像加速"
            ;;
        *)
            warn "无效选项，使用默认: GitHub 官方直连"
            ;;
    esac
    echo ""
}

# ---------- 应用镜像（非交互模式，通过 GITHUB_MIRROR 环境变量） ----------
apply_mirror() {
    case "${GITHUB_MIRROR:-official}" in
        gh-proxy)
            BASE_URL="https://gh-proxy.com/https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
            ;;
        ghfast)
            BASE_URL="https://ghfast.top/https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
            ;;
        *)
            BASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${RELEASE_VERSION}"
            ;;
    esac
}

# ---------- 软件包状态检测 ----------
is_installed() {
    opkg list-installed 2>/dev/null | awk -v pkg="$1" '{ if ($1 == pkg) found=1 } END { exit !found }'
}

# ---------- 下载 ----------
download_pkgs() {
    mkdir -p "$TMPDIR" || return 1
    info "下载 $PKG_MAIN ..."
    curl -kL --fail --max-time 120 -o "$TMPDIR/$PKG_MAIN" "$BASE_URL/$PKG_MAIN" || return 1
    info "下载 $PKG_LUCI ..."
    curl -kL --fail --max-time 120 -o "$TMPDIR/$PKG_LUCI" "$BASE_URL/$PKG_LUCI" || return 1
}

cleanup() {
    rm -rf "$TMPDIR"
}

# ---------- 安装 ----------
do_install() {
    check_env
    if is_installed cqiptv && is_installed luci-app-cqiptv; then
        warn "已安装 cqiptv / luci-app-cqiptv。"
        warn "如需更新请执行: sh install.sh update"
        warn "如需强制重装请执行: sh install.sh reinstall"
        return 0
    fi
    info "opkg update ..."
    opkg update || { err "opkg update 失败"; exit 1; }
    download_pkgs || { err "下载失败"; cleanup; exit 1; }
    info "安装软件包 ..."
    opkg install "$TMPDIR/$PKG_MAIN" "$TMPDIR/$PKG_LUCI" || { err "安装失败"; cleanup; exit 1; }
    cleanup
    info "启用并启动服务 ..."
    /etc/init.d/cqiptv enable && /etc/init.d/cqiptv start
    info "安装完成。LuCI: 服务 -> IPTV 采集"
}

# ---------- 更新 ----------
do_update() {
    check_env
    if ! is_installed cqiptv; then
        warn "尚未安装，将执行安装。"
        do_install
        return 0
    fi
    info "opkg update ..."
    opkg update || { err "opkg update 失败"; exit 1; }
    download_pkgs || { err "下载失败"; cleanup; exit 1; }
    info "更新软件包 ..."
    opkg install --force-reinstall "$TMPDIR/$PKG_MAIN" "$TMPDIR/$PKG_LUCI" || { err "更新失败"; cleanup; exit 1; }
    cleanup
    info "重启服务 ..."
    /etc/init.d/cqiptv restart 2>/dev/null || /etc/init.d/cqiptv start
    info "更新完成。"
}

# ---------- 强制重装 ----------
do_reinstall() {
    check_env
    info "opkg update ..."
    opkg update || { err "opkg update 失败"; exit 1; }
    download_pkgs || { err "下载失败"; cleanup; exit 1; }
    info "强制重装软件包 ..."
    opkg install --force-reinstall "$TMPDIR/$PKG_MAIN" "$TMPDIR/$PKG_LUCI" || { err "重装失败"; cleanup; exit 1; }
    cleanup
    /etc/init.d/cqiptv restart 2>/dev/null || /etc/init.d/cqiptv start
    info "强制重装完成。"
}

# ---------- 卸载 ----------
# 用法: do_uninstall [purge]
#   purge    卸载同时删除 /etc/cqiptv 运行时数据（不保留数据）
do_uninstall() {
    local purge="${1:-}"
    if ! is_installed cqiptv && ! is_installed luci-app-cqiptv; then
        warn "未安装 cqiptv，无需卸载。"
        if [ "$purge" = "purge" ]; then
            [ -d /etc/cqiptv ] && { info "删除运行时数据 /etc/cqiptv ..."; rm -rf /etc/cqiptv; }
        fi
        return 0
    fi
    info "停止并禁用服务 ..."
    /etc/init.d/cqiptv stop 2>/dev/null || true
    /etc/init.d/cqiptv disable 2>/dev/null || true
    info "卸载软件包 ..."
    opkg remove luci-app-cqiptv cqiptv
    if [ "$purge" = "purge" ]; then
        # 清理安装临时文件
        rm -rf /tmp/cqiptv-install-* 2>/dev/null || true
        # 彻底删除：运行时数据目录（config.yaml、output m3u/epg、data/icon、data/epg_cache、log）
        if [ -d /etc/cqiptv ]; then
            info "删除运行时数据 /etc/cqiptv（配置/M3U/EPG/图标/日志）..."
            rm -rf /etc/cqiptv
        fi
        # UCI 配置（opkg 卸载默认保留 conffile，这里一并删除）
        if [ -f /etc/config/cqiptv ]; then
            info "删除 UCI 配置 /etc/config/cqiptv ..."
            rm -f /etc/config/cqiptv
        fi
        # 验证删除结果
        if [ -d /etc/cqiptv ] || [ -f /etc/config/cqiptv ]; then
            err "数据清除不完整，请手动检查 /etc/cqiptv 与 /etc/config/cqiptv。"
        else
            info "卸载完成（配置、M3U、EPG、图标等数据已全部清除）。"
        fi
    else
        info "卸载完成。"
        info "提示: 运行时数据保留在 /etc/cqiptv，彻底删除请执行: sh install.sh uninstall-full"
    fi
}

# ---------- 状态查看 ----------
do_status() {
    echo "=== 环境 ==="
    uname -a
    opkg print-architecture 2>/dev/null | tr '\n' ' '; echo
    echo "=== 已安装包 ==="
    if is_installed cqiptv; then opkg list-installed 2>/dev/null | grep '^cqiptv'; else echo "cqiptv: 未安装"; fi
    if is_installed luci-app-cqiptv; then opkg list-installed 2>/dev/null | grep '^luci-app-cqiptv'; else echo "luci-app-cqiptv: 未安装"; fi
    echo "=== 服务状态 ==="
    if /etc/init.d/cqiptv enabled >/dev/null 2>&1; then
        echo "开机自启: 已启用"
    else
        echo "开机自启: 未启用"
    fi
    if command -v netstat >/dev/null 2>&1 && netstat -ltn 2>/dev/null | grep -q ':6061'; then
        echo "Web 服务: 运行中 (端口 6061)"
    else
        echo "Web 服务: 未检测到 6061 端口监听"
    fi
}

# ---------- 交互主菜单 ----------
interactive_menu() {
    while :; do
        echo ""
        echo "=========================================="
        echo "  cqiptv OpenWrt 一键管理"
        echo "=========================================="
        echo ""
        echo "  1) 安装"
        echo "  2) 更新到最新版"
        echo "  3) 强制重装"
        echo "  4) 卸载（保留 /etc/cqiptv 数据）"
        echo "  5) 卸载（不保留数据）"
        echo "  6) 查看状态"
        echo "  7) 退出"
        echo ""
        printf "请输入选项 [1-7] (默认: 1): "
        read choice < /dev/tty || choice="1"
        [ -z "$choice" ] && choice="1"
        echo ""
        case "$choice" in
            1) do_install; return 0 ;;
            2) do_update; return 0 ;;
            3) do_reinstall; return 0 ;;
            4) do_uninstall; return 0 ;;
            5) do_uninstall purge; return 0 ;;
            6) do_status; return 0 ;;
            7) info "已退出"; return 0 ;;
            *) warn "无效选项，请重新输入 [1-7]" ;;
        esac
    done
}

show_help() {
    cat <<EOF
cqiptv OpenWrt 一键管理脚本
用法: sh install.sh [命令]

命令列表:
  （无参数）   交互模式（菜单选择）
  install      安装
  update       更新到最新版
  reinstall    强制重装（覆盖已安装文件）
  uninstall    卸载（保留 /etc/cqiptv 数据）
  uninstall-full 卸载并清除全部数据（配置/M3U/EPG/图标及 UCI 配置）
  status       查看环境/安装/服务状态
  help         显示本帮助

环境变量:
  GITHUB_MIRROR=official|gh-proxy|ghfast   指定 GitHub 访问方式（非交互模式）

示例:
  sh install.sh
  sh install.sh update
  sh install.sh reinstall
EOF
}

case "$ACTION" in
    ""|interactive)
        select_github_mirror
        interactive_menu
        ;;
    install)
        apply_mirror
        do_install
        ;;
    update)
        apply_mirror
        do_update
        ;;
    reinstall)
        apply_mirror
        do_reinstall
        ;;
    uninstall)
        apply_mirror
        do_uninstall
        ;;
    uninstall-full|purge)
        apply_mirror
        do_uninstall purge
        ;;
    status)
        do_status
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        err "未知命令: $ACTION"
        show_help
        exit 1
        ;;
esac