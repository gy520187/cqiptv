# ========== 构建阶段 ==========
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ========== 运行阶段 ==========
FROM python:3.11-slim

# 时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 中文字体（用于图标占位图）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-zenhei \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 创建用户
RUN useradd -m -u 1000 iptv

WORKDIR /app

# 从构建阶段复制依赖
COPY --from=builder /root/.local /home/iptv/.local

# 复制项目
COPY --chown=iptv:iptv . .

# 启动前检查脚本
COPY --chown=iptv:iptv docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 创建目录
RUN mkdir -p /app/data/icon /app/output /app/log \
    && chown -R iptv:iptv /app

USER iptv

# 环境变量
ENV PATH=/home/iptv/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 端口
EXPOSE 6060

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:6060/', timeout=3)"

# 默认启动 Web（ENTRYPOINT 做挂载与权限预检）
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "server.py"]