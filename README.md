# IPTV 采集工具

自动获取 IPTV 频道列表、EPG 节目单，生成第三方播放器可用的 M3U 和 XMLTV 数据源。

## 功能

- 频道列表采集与归一化（自动注入缺失的 4K 频道）
- EPG 节目单采集：同名变体备用 ID 回退、历史 7 天、外部 EPG 源补充（运营商数据优先）
- 媒体编码映射与组播地址解析（含 FCC 快速切台）
- 归一化 M3U：catchup 回看、频道自动分类、CCTV 按编号排序
- 频道图标下载
- Web 管理界面（默认端口 6060）
- 定时自动采集

## 快速开始

### 本地运行

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
python server.py        # Web 界面: http://localhost:6060
python main.py          # 命令行采集
python scheduler.py     # 定时采集
```

### Docker 部署

```bash
cp config.example.yaml config.yaml
mkdir -p data output log
chown -R 1000:1000 config.yaml data output log
docker compose up -d --build
```

`config.yaml` 必须预先存在，否则 Docker 会把挂载点创建成目录导致容器启动失败。

## 配置

### .env（参考 .env.example）

| 变量 | 说明 |
|------|------|
| `WEB_PORT` | 宿主机端口（默认 6060） |
| `ICON_HOST` | M3U 图标地址，需为播放器可达的 URL |
| `EPG_URL` | M3U 首行 x-tvg-url，默认 `ICON_HOST/epg.xml.gz` |
| `WEB_AUTH` | 外网访问鉴权，格式 `user:password`，公网暴露必须启用 |
| `EXTERNAL_EPG_URL` | 外部 EPG 补充源（逗号分隔多个），留空禁用 |

### config.yaml

| 字段 | 说明 |
|------|------|
| `AuthenticationIP` | 认证服务器地址 |
| `UserID` | 用户账号 |
| `mac` | MAC 地址 |
| `STBID` | 机顶盒序列号 |
| `STBType` | 机顶盒型号 |
| `STBVersion` | 机顶盒版本 |
| `SoftwareVersion` | 软件版本 |
| `ip` | 机顶盒 IP（认证参数） |
| `SessionID` | 会话 ID（可选） |
| `Authenticator` | 硬件签名（可选，用于破解 key） |
| `key` | DES 密钥（自动回写） |

## 第三方播放器接入

- M3U: `http://your-server:6060/playlist.m3u`
- EPG: `http://your-server:6060/epg.xml.gz`
- 图标: `http://your-server:6060/data/icon/{name}.png`

## 目录结构

- `output/`：采集结果（channels.json / epg.xml / playlist.m3u）
- `data/icon/`：频道图标
- `log/`：日志

## 注意事项

- 需自行获取有效的 `SessionID`（从机顶盒抓包）
- `Authenticator` 用于自动破解 key
- 仅供学习研究，请勿用于商业用途