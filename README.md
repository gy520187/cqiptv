# IPTV 采集工具

自动获取 IPTV 频道列表、EPG 节目单，生成第三方播放器可用的 M3U 和 XMLTV 数据源。

## 功能

- ✅ 频道列表采集（225 频道 → 过滤后 ~140）
- ✅ EPG 节目单采集（XMLTV 格式）
- ✅ 媒体编码映射（探针用）
- ✅ 组播地址解析（含 FCC 快速切台）
- ✅ 归一化 M3U（catchup 回看 + 频道自动分类）
- ✅ 图标下载（fanmingming 图标库）
- ✅ DES 密钥破解（Authenticator，8 位数字 key）
- ✅ Web 管理界面（端口 6060）
- ✅ 定时自动采集

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化配置

```bash
cp config.example.yaml config.yaml
```

或直接启动 Web 界面，首次运行会引导配置。

### 3. 启动 Web 界面

```bash
python server.py
```

浏览器访问 http://localhost:6060/，首次进入会自动跳转配置页。

### 4. 采集数据

在 Web 界面点"采集"按钮，或命令行：

```bash
python main.py
```

key 缺失或失效时，默认会报错退出（避免静默跑数小时破解）。如需命令行自动破解，加 `--crack` 参数：

```bash
python main.py --crack
```

### 5. 定时采集（可选）

```bash
python scheduler.py
```

## Docker 部署

首次部署前，在宿主机项目目录准备好配置和目录（容器以 uid 1000 运行）：

```bash
cp config.example.yaml config.yaml
mkdir -p data output log
chown -R 1000:1000 config.yaml data output log
docker compose up -d --build
```

注意：config.yaml 必须预先存在，否则 Docker 会把挂载点创建成目录，容器启动即失败（entrypoint 会给出明确报错）。

宿主机端口和图标地址通过 `.env` 配置（参考 `.env.example`）：

```bash
cp .env.example .env
# 修改 WEB_PORT（宿主机端口）和 ICON_HOST（播放器可达的图标地址）
```

M3U 中的图标地址来自 ICON_HOST，需改成第三方播放器实际能访问到的地址（如局域网 IP）。

## 外网 IPv6 访问

1. `.env` 中设置 `WEB_AUTH=用户名:密码`——公网暴露必须启用，否则任何人都能通过 `/api/config` 读取机顶盒凭据
2. iStoreOS 防火墙放行（IPv6 无 NAT，只需放行入站）：LuCI → 网络 → 防火墙 → 通信规则，新建规则：协议 TCP、源区域 wan、目标端口 6060、动作接受
3. 确认 DDNS 写入的是 IPv6 地址：`nslookup -type=AAAA iptv.20221122.xyz`
4. 外网设备（手机开蜂窝数据）访问 `http://iptv.20221122.xyz:6060/`
5. 外网播放器使用 M3U 时，把 `.env` 的 `ICON_HOST` 改为 `http://iptv.20221122.xyz:6060`，图标地址需外网可达

## 局域网无法访问 6060 端口的排查

依次执行：

```bash
docker compose ps
docker logs iptv-web --tail 50
curl -s http://127.0.0.1:6060/api/status
```

- 容器状态为 Restarting/Exited：看 logs，常见原因是 config.yaml 缺失或目录属主非 uid 1000
- 容器正常且宿主机本机 curl 通、局域网其他机器不通：检查宿主机防火墙（ufw / NAS 防火墙）是否放行 6060
- 浏览器报 ERR_UNSAFE_PORT（curl 正常）：Chrome/Edge 禁止访问 6000/6001 等 X11 端口，这就是默认端口采用 6060 的原因；如自行改过 WEB_PORT，避开禁用名单即可

## 第三方播放器接入

数据源 URL
M3U http://your-server:6060/playlist.m3u
EPG http://your-server:6060/epg.xml.gz
图标 http://your-server:6060/data/icon/{name}.png

配置文件

仅需 11 个字段：

```yaml
AuthenticationIP: ""    # 认证服务器地址
UserID: ""              # 用户账号
mac: ""                 # MAC 地址
STBID: ""               # 机顶盒序列号
STBType: ""             # 机顶盒型号
STBVersion: ""          # 机顶盒版本
SoftwareVersion: ""     # 软件版本，如 19.2.0-LCQD15.B011
ip: ""                  # 机顶盒 IP（认证参数）
SessionID: ""           # 会话 ID（可选）
Authenticator: ""       # 硬件签名（可选，用于破解 key）
key: ""                 # DES 密钥（自动回写）
```

其余配置写死在 iptv/constants.py。

目录说明

· output/：采集结果（channels.json / epg.xml / playlist.m3u）
· data/icon/：频道图标
· log/：日志

注意事项

· 需自行获取有效的 SessionID（从机顶盒抓包）
· Authenticator 用于自动破解 key
· 仅供学习研究，请勿用于商业用途