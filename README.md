# IPTV 采集工具

自动获取 IPTV 频道列表、EPG 节目单，生成第三方播放器可用的 M3U 和 XMLTV 数据源。

## 功能

- ✅ 频道列表采集（225 频道 → 过滤后 ~140）
- ✅ EPG 节目单采集（XMLTV 格式）
- ✅ 媒体编码映射（探针用）
- ✅ 组播地址解析（含 FCC 快速切台）
- ✅ 归一化 M3U（catchup 回看）
- ✅ 图标下载（fanmingming 图标库）
- ✅ 3DES 密钥破解（Authenticator）
- ✅ Web 管理界面（端口 6000）
- ✅ 定时自动采集

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 初始化配置

```bash
cp config.example.yaml config.yaml
```

或直接启动 Web 界面，首次运行会引导配置。

3. 启动 Web 界面

```bash
python server.py
```

浏览器访问 http://localhost:6000/，首次进入会自动跳转配置页。

4. 采集数据

在 Web 界面点"采集"按钮，或命令行：

```bash
python main.py
```

5. 定时采集（可选）

```bash
python scheduler.py
```

第三方播放器接入

数据源 URL
M3U http://your-server:6000/playlist.m3u
EPG http://your-server:6000/epg.xml.gz
图标 http://your-server:6000/data/icon/{name}.png

配置文件

仅需 8 个字段：

```yaml
AuthenticationIP: ""    # 认证服务器地址
UserID: ""              # 用户账号
mac: ""                 # MAC 地址
STBID: ""               # 机顶盒序列号
STBType: ""             # 机顶盒型号
STBVersion: ""          # 机顶盒版本
Authenticator: ""       # 硬件签名（可选，用于破解 key）
key: ""                 # 3DES 密钥（自动回写）
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