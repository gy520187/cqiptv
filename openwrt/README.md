# OpenWrt 24.10 打包（含 LuCI）

本目录提供两个 OpenWrt 软件包：

| 包名 | 说明 |
|---|---|
| `cqiptv` | 主程序：Flask Web 管理 + 采集器 + 定时任务，数据存于 `/etc/cqiptv` |
| `luci-app-cqiptv` | LuCI 界面：状态查看、触发采集、输出文件下载、日志查看 |

## 依赖处理

OpenWrt 24.10 官方源中**没有 `python3-apscheduler` 和 `python3-tzlocal`**，
因此已将其纯 Python 代码捆绑到 `cqiptv/files/usr/share/cqiptv/vendor/`，
启动脚本通过 `PYTHONPATH` 引用。其余依赖均来自官方源：

- `python3-flask`、`python3-requests`、`python3-yaml`
- `python3-ruamel-yaml`、`python3-cryptodome`、`python3-pillow`
- `python3-pytz`、`python3-six`

## 编译

将两个包目录放入 OpenWrt SDK 的 `package/` 目录：

```bash
cp -r cqiptv luci-app-cqiptv /path/to/sdk/package/
cd /path/to/sdk
./scripts/feeds update -a
./scripts/feeds install -a   # 若 SDK 用 feeds 管理包
make menuconfig
```

在 menuconfig 中勾选：

```
Network  -> IPTV -> cqiptv
LuCI    -> 3. Applications -> luci-app-cqiptv
```

编译：

```bash
make package/cqiptv/compile V=s
make package/luci-app-cqiptv/compile V=s
```

生成的 `.ipk` 位于 `bin/packages/<arch>/packages/` 或 `bin/targets/.../packages/`。

## 安装

### 一键管理脚本（GitHub Release，x86_64）

已发布到 GitHub Releases，适用于 OpenWrt 24.10 x86_64 路由器（含 iStoreOS）。推荐使用一键管理脚本，自动检测平台/架构、检查安装状态，支持安装、更新、强制重装、卸载：

```bash
uclient-fetch -q -O - https://raw.githubusercontent.com/gy520187/cqiptv/main/openwrt/install.sh | sh
```

```bash
uclient-fetch -q -O - https://raw.githubusercontent.com/gy520187/cqiptv/main/openwrt/install.sh | sh                 # 安装
uclient-fetch -q -O - https://raw.githubusercontent.com/gy520187/cqiptv/main/openwrt/install.sh | sh -s update      # 更新到最新版
uclient-fetch -q -O - https://raw.githubusercontent.com/gy520187/cqiptv/main/openwrt/install.sh | sh -s reinstall   # 强制重装
uclient-fetch -q -O - https://raw.githubusercontent.com/gy520187/cqiptv/main/openwrt/install.sh | sh -s uninstall   # 卸载（保留 /etc/cqiptv 数据）
uclient-fetch -q -O - https://raw.githubusercontent.com/gy520187/cqiptv/main/openwrt/install.sh | sh -s status      # 查看状态
```

备选：手动下载安装（推荐用 `curl`，能可靠跟随 GitHub 下载重定向）：

```bash
opkg update && \
curl -kL -o /tmp/cqiptv.ipk https://github.com/gy520187/cqiptv/releases/download/v1.0.0/cqiptv_1.0.0-1_x86_64.ipk && \
curl -kL -o /tmp/luci-app-cqiptv.ipk https://github.com/gy520187/cqiptv/releases/download/v1.0.0/luci-app-cqiptv_1.0.0-1_x86_64.ipk && \
opkg install /tmp/cqiptv.ipk /tmp/luci-app-cqiptv.ipk && \
rm -f /tmp/cqiptv.ipk /tmp/luci-app-cqiptv.ipk && \
/etc/init.d/cqiptv enable && \
/etc/init.d/cqiptv start
```

无 `curl` 时先 `opkg install curl`，或用 `wget --no-check-certificate -q -O /tmp/xxx.ipk <同款 URL>` 下载后安装；若报 `Malformed package file`，改用上面的 `curl` 版本。

### 本地 .ipk 安装

```bash
opkg install cqiptv_*.ipk luci-app-cqiptv_*.ipk
```

安装后启动：

```bash
/etc/init.d/cqiptv enable
/etc/init.d/cqiptv start
```

LuCI 菜单「服务 -> IPTV 采集」即可打开管理页。

## 配置（UCI）

编辑 `/etc/config/cqiptv`：

```
config cqiptv 'web'
	option port '6061'                      # Flask 服务端口（OpenWrt 版固定 6061，与 Docker 版 6060 区分）
	option auth 'user:password'             # 可选 Basic 认证，留空不启用
	option icon_host 'http://192.168.1.1:6061'  # M3U 图标地址（改路由器实际 IP）
	option epg_url ''                       # M3U x-tvg-url，留空用默认
	option epg_workers '2'                  # EPG 并行线程数

config cqiptv 'scheduler'
	option enabled '0'                      # 1 启用定时采集
	option cron '0 4 * * *'                 # cron 表达式
```

修改后重启：`/etc/init.d/cqiptv restart`。

采集相关账号配置（`AuthenticationIP`、`UserID`、`mac`、`STBID` 等）首次打开
管理页时在 Web 界面填写，保存在 `/etc/cqiptv/config.yaml`。

## 运行时数据

- 工作目录：`/etc/cqiptv/`
  - `config.yaml`：账号/密钥配置（Web 管理页维护）
  - `data/`：EPG 缓存、图标
  - `output/`：`playlist.m3u`、`epg.xml(.gz)`、`channels.json`、`epg.json`、`iptv.db`
  - `log/iptv.log`：运行日志

## 注意事项

- LuCI 页面通过 `http://<路由器IP>:6061` 跨端口调用 Flask API。
  请使用 **HTTP** 访问 LuCI（OpenWrt 默认），若启用 HTTPS 需为 6061 配置反向代理，
  否则浏览器会阻止混合内容。
- 若从公网访问，请在防火墙放行 6061 端口并设置 `auth`（Basic 认证）。
- 输出文件的播放器订阅地址：`http://<路由器IP>:6061/playlist.m3u`、
  `http://<路由器IP>:6061/epg.xml.gz`。

## 版本更新

更新项目代码后，重新同步 `cqiptv/files/usr/share/cqiptv/` 下的
`main.py`、`scheduler.py`、`server.py`、`iptv/`、`web/`、`config.example.yaml`
（`vendor/` 一般无需变动），然后重新编译即可。