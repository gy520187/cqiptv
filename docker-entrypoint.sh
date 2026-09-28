#!/bin/sh
set -e

APP_ROOT="${APP_ROOT:-/app}"

# 陷阱 1: 宿主机缺少 config.yaml 时，Docker 会把挂载点创建成目录
if [ -d "$APP_ROOT/config.yaml" ]; then
    echo "[entrypoint] 错误: $APP_ROOT/config.yaml 是目录，说明宿主机上缺少该文件" >&2
    echo "[entrypoint] 请先在宿主机项目目录执行: bash init.sh（会自动生成 config.yaml）" >&2
    echo "[entrypoint] 若已生成过，可手动执行: cp config.example.yaml config.yaml" >&2
    exit 1
fi

# 陷阱 2: 容器以 uid 1000 运行，挂载目录属主不符时写入会失败
for d in "$APP_ROOT/log" "$APP_ROOT/output" "$APP_ROOT/data"; do
    if [ -e "$d" ] && [ ! -w "$d" ]; then
        echo "[entrypoint] 错误: $d 不可写（宿主机目录属主需为 uid 1000）" >&2
        echo "[entrypoint] 请在宿主机项目目录执行: mkdir -p data output log && chown -R 1000:1000 data output log config.yaml" >&2
        exit 1
    fi
done

# 陷阱 3: config.yaml 必须可写，否则 Web 保存配置/定时任务会报 Permission denied
if [ -e "$APP_ROOT/config.yaml" ] && [ ! -w "$APP_ROOT/config.yaml" ]; then
    echo "[entrypoint] 错误: $APP_ROOT/config.yaml 不可写（宿主机文件属主需为 uid 1000）" >&2
    echo "[entrypoint] 请在宿主机项目目录执行: chown 1000:1000 config.yaml && chmod 664 config.yaml" >&2
    exit 1
fi

exec "$@"
