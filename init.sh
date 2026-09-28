#!/bin/bash
# ============================================================
# IPTV 项目初始化脚本（重庆电信 / 华为机顶盒）
# 首次运行前执行: bash init.sh
# 自动检测并生成 .env 与 config.yaml，创建数据目录并设置权限
# ============================================================
set -e
cd "$(dirname "$0")"

echo "==> IPTV 项目初始化"

# ---------- .env ----------
if [ -f .env ]; then
    echo "  .env 已存在，跳过"
else
    cp .env.example .env
    echo "  已生成 .env（请修改 ICON_HOST 为播放器可达地址，必要时设置 WEB_AUTH）"
fi

# ---------- config.yaml ----------
if [ -d config.yaml ]; then
    echo "  [错误] config.yaml 是目录，不是文件。"
    echo "  原因：缺少 config.yaml 时直接执行 docker compose up，Docker 把挂载点创建成了目录。"
    echo "  修复：请先手动删除该目录，再重新运行本脚本："
    echo "      rm -rf config.yaml && bash init.sh"
    exit 1
fi
if [ -f config.yaml ]; then
    echo "  config.yaml 已存在，跳过"
else
    cp config.example.yaml config.yaml
    echo "  已生成 config.yaml（请填入从机顶盒抓包获取的认证参数）"
fi

# ---------- 数据目录 ----------
mkdir -p data output log
echo "  数据目录 data/ output/ log/ 已就绪"

# ---------- 权限（Docker 容器以 uid 1000 运行） ----------
if [ "$(id -u)" = "0" ]; then
    chown -R 1000:1000 config.yaml data output log
    echo "  已设置 config.yaml 与数据目录属主为 uid 1000"
else
    echo "  提示：当前非 root 用户，Docker 部署时请手动执行："
    echo "      sudo chown -R 1000:1000 config.yaml data output log"
fi

echo ""
echo "==> 初始化完成。下一步："
echo "    1) 编辑 config.yaml，填入抓包获取的认证参数"
echo "    2) 编辑 .env，设置 ICON_HOST（播放器可达地址）"
echo "    3) 启动服务："
echo "       - Docker 部署: docker compose up -d --build"
echo "       - 本地运行:   pip install -r requirements.txt && python server.py"