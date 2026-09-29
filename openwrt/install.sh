#!/bin/sh
# cqiptv OpenWrt 一键安装/更新/卸载脚本
# 适用: OpenWrt 24.10 x86_64 / iStoreOS x86_64
#
# 用法:
#   sh install.sh               安装（默认）
#   sh install.sh install      安装
#   sh install.sh update       更新到最新版
#   sh install.sh reinstall    强制重装
#   sh install.sh uninstall    卸载
#   sh install.sh status       查看状态
#   sh install.sh help          帮助

set -u

# 下载地址（后续版本更新时只需修改资产文件名）
BASE_URL="https://github.com/gy520187/cqiptv/releases/latest/download"
PKG_MAIN="cqiptv_1.0.0-1_x86_64.ipk"
PKG_LUCI="luci-app-cqiptv_1.0.0-1_x86_64.ipk"
ARCH="x86_64"

ACTION="${1:-install}"
TMPDIR="/tmp/cqiptv-install-$$"

info()  { echo "[INFO] $*"; }
warn()  { echo "[WARN] $*"; }
err()   { echo "[ERROR] $*" >&2; }

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
        err "无法访问 GitHub Release（$BASE_URL），请检查网络。"
        exit 1
    fi
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

# ---------- 卸载（保留 /etc/cqiptv 数据） ----------
do_uninstall() {
    if ! is_installed cqiptv && ! is_installed luci-app-cqiptv; then
        warn "未安装 cqiptv，无需卸载。"
        return 0
    fi
    info "停止并禁用服务 ..."
    /etc/init.d/cqiptv stop 2>/dev/null || true
    /etc/init.d/cqiptv disable 2>/dev/null || true
    info "卸载软件包 ..."
    opkg remove luci-app-cqiptv cqiptv
    info "卸载完成。"
    info "提示: 运行时数据保留在 /etc/cqiptv，如需彻底删除请手动执行: rm -rf /etc/cqiptv"
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

show_help() {
    cat <<EOF
cqiptv OpenWrt 一键管理脚本
用法: sh install.sh [命令]

命令列表:
  install      安装（默认）
  update       更新到最新版
  reinstall    强制重装（覆盖已安装文件）
  uninstall    卸载（保留 /etc/cqiptv 数据）
  status       查看环境/安装/服务状态
  help         显示本帮助

示例:
  sh $0 install
  sh $0 update
  sh $0 reinstall
  sh $0 uninstall
EOF
}

case "$ACTION" in
    install)       do_install ;;
    update)        do_update ;;
    reinstall)     do_reinstall ;;
    uninstall)     do_uninstall ;;
    status)         do_status ;;
    help|-h|--help) show_help ;;
    *) err "未知命令: $ACTION"; show_help; exit 1 ;;
esac