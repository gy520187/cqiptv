# IPTV 采集工具（重庆电信）

自动获取重庆电信 IPTV 频道列表、EPG 节目单，生成第三方播放器可用的 M3U 和 XMLTV 数据源。

> **适用性声明**：本项目只适用于重庆电信 IPTV，并仅在华为机顶盒平台（EC6108V9U 系列）验证成功。其他地区、其他运营商、其他品牌机顶盒的认证流程和接口可能不同，无法保证可用。

## 重要提醒（必读）

**使用前必须先打通 IPTV 线路并完成抓包**，否则工具无法工作：

1. **打通 IPTV 线路**：IPTV 业务必须已在重庆电信宽带下正常开通，光猫/路由器需正确配置 IPTV 通道（机顶盒能正常看直播）。
2. **抓包获取认证参数**：机顶盒开机认证时与运营商认证服务器通信，需要用抓包工具（Wireshark 等，可配合机顶盒所在网段镜像）抓取认证请求中的关键参数，包括认证服务器地址、UserID、MAC、STBID、STBType、STBVersion、SoftwareVersion、Authenticator 等。
3. 抓包得到的参数填入 `config.yaml` 后，工具才能模拟机顶盒完成认证并采集频道/EPG。

## 功能

- 频道列表采集与归一化（自动注入缺失的 4K 频道）
- EPG 节目单采集：同名变体备用 ID 回退、历史 7 天、外部 EPG 源补充（运营商数据优先）
- 媒体编码映射与组播地址解析（含 FCC 快速切台）
- 归一化 M3U：catchup 回看、频道自动分类、CCTV 按编号排序
- 频道图标下载
- Web 管理界面（默认端口 6060）
- 定时自动采集（保存配置后自动生效）

## 工作原理

1. 用抓包获取的认证参数向重庆电信认证服务器发起认证，拿到会话凭证。
2. 凭证请求频道列表、组播地址、媒体编码、EPG 节目单等接口。
3. 数据归一化后输出 `playlist.m3u`、`epg.xml`、`epg.xml.gz`、`channels.json`。
4. 第三方播放器通过 Web 服务直接订阅 M3U / EPG 数据源。

认证所需的 3DES 密钥（`key`）通过暴力破解获得，破解成功后自动回写到 `config.yaml`。

## 部署前准备：抓包参数

在机顶盒抓包中查找以下字段，填入 `config.yaml`：

| 字段 | 说明 | 示例 |
|------|------|------|
| `AuthenticationIP` | 认证服务器地址 | `http://172.23.88.159:33200/EPG/jsp` |
| `UserID` | 用户账号 | `i5207379189@itv` |
| `mac` | MAC 地址 | `28:A6:DB:6F:D2:9E` |
| `STBID` | 机顶盒序列号 | `0010049900608930173628A6DB6FD29E` |
| `STBType` | 机顶盒型号 | `EC6108V9U_pub_cqydx` |
| `STBVersion` | 机顶盒版本 | `HWV215011P0000` |
| `SoftwareVersion` | 软件版本 | `19.2.0-LCQD15.B011` |
| `Authenticator` | 抓包获取的硬件签名（十六进制） | 见抓包 |
| `key` | 3DES 密钥（破解成功后自动回写） | 留空即可 |

## 快速开始

### Docker 部署（推荐）

```bash
# 1. 准备配置
cp config.example.yaml config.yaml
cp .env.example .env

# 2. 编辑 .env，把 ICON_HOST 改成播放器可达的地址（如局域网 IP）
#    vim .env

# 3. 编辑 config.yaml，填入抓包获取的认证参数
#    vim config.yaml

# 4. 创建数据目录并设置权限（容器以 uid 1000 运行）
mkdir -p data output log
chown -R 1000:1000 config.yaml data output log

# 5. 启动
docker compose up -d --build
```

`config.yaml` 必须预先存在，否则 Docker 会把挂载点创建成目录导致容器启动失败。

### 本地运行

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # 填入抓包参数
python server.py        # Web 界面: http://localhost:6060
python main.py          # 命令行采集（一次性）
python scheduler.py    # 定时采集
```

## Web 界面使用

浏览器打开 `http://<服务器IP>:6060`。

首次运行时配置不完整（`key` 为空），会自动跳转到 **配置** 页面：

1. **配置页**：填入抓包获取的认证参数，点击「保存」，再点击「连接测试」验证参数是否可用。
2. **破解页**：`key` 未破解时在此发起暴力破解（可设起始/结束/进程数），破解成功后 `key` 自动回写到 `config.yaml`。
3. **总览页**：点击「开始采集」，页面实时显示采集进度；完成后可下载 `playlist.m3u`、`epg.xml`、`epg.xml.gz`。
4. **频道页**：浏览采集到的频道列表及组播/回看地址。
5. **EPG 页**：按频道查看节目单。
6. **定时任务页**：设置 cron 表达式（默认每天 04:00），支持多个任务；保存后 scheduler 自动重新加载，无需重启容器。
7. **日志页**：查看采集与调度日志。

## 第三方播放器接入

Web 服务提供以下数据源（播放器直接订阅，免鉴权）：

```
M3U:  http://<服务器IP>:6060/playlist.m3u
EPG:  http://<服务器IP>:6060/epg.xml.gz
图标: http://<服务器IP>:6060/data/icon/<频道名>.png
```

注意：`.env` 中的 `ICON_HOST` 必须配置为播放器能访问到的地址（如局域网 IP `http://192.168.1.100:6060`），否则 M3U 中的图标地址播放器无法加载。

## 定时任务

- 默认每天 04:00 自动采集一次（避开高峰期）。
- 支持多任务：在 Web「定时任务」页维护，每个任务包含一条 cron 表达式。
- 保存配置后 scheduler 会在几秒内自动重新加载新配置，无需重启容器。
- 调度日志位于 `log/`。

## 目录结构

```
config.yaml          # 认证配置（含敏感信息，勿提交/外传）
config.example.yaml # 配置模板
.env.example        # Docker Compose 环境变量模板
output/              # 采集结果
  ├── channels.json  # 频道列表
  ├── epg.json        # EPG 原始数据
  ├── epg.xml         # XMLTV 节目单
  ├── epg.xml.gz       # 压缩版节目单（播放器推荐入口）
  └── playlist.m3u    # 归一化 M3U
data/icon/          # 频道图标
log/                 # 运行日志
web/                 # Web 前端
iptv/                # 采集核心模块
```

## 辅助脚本

```bash
# 检查缺失的频道图标
python tools/check_icons.py

# 手动下载所有频道图标
python tools/download_icons.py

# 容器内手动拉取单个频道 EPG（用于排查频道）
docker compose exec -T iptv-scheduler python - < scripts/fetch_epg.py 云南卫视

# 诊断单频道 EPG 原始响应
docker compose exec -T iptv-scheduler python - < scripts/debug_epg_raw.py
```

## 注意事项

- 必须在重庆电信 IPTV 线路已打通的环境下运行，并需先从机顶盒抓包获取认证参数。
- `config.yaml` 含敏感认证信息，已被 `.gitignore` 忽略，请勿提交或外传。
- 仅华为机顶盒平台验证成功，其他平台可能不适用。
- 仅供学习研究，请勿用于商业用途。