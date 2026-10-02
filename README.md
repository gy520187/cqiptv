# OpenWrt 24.10 打包（含 LuCI）

本目录提供两个 OpenWrt 软件包：

| 包名 | 说明 |
|---|---|
| `cqiptv` | 主程序：Flask Web 管理 + 采集器 + 定时任务，数据存于 `/etc/cqiptv` |
| `luci-app-cqiptv` | LuCI 界面：状态查看、触发采集、输出文件下载、日志查看 |

`cqiptv` 包**内置 112 个常用频道图标**（安装后自动复制到 `/etc/cqiptv/data/icon`，不覆盖已有图标），未内置的新频道图标采集时仍会在线下载。

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

已发布到 GitHub Releases，适用于 OpenWrt 24.10 x86_64 路由器（含 iStoreOS）。推荐使用一键管理脚本（可互动：先选择 GitHub 访问方式，再进入操作菜单；支持安装、更新、强制重装、卸载）：

```bash
# 交互模式：选择 GitHub 访问方式（官方直连 / gh-proxy.com / ghfast.top 镜像）后进入操作菜单
uclient-fetch -q --no-check-certificate -O - https://github.com/gy520187/cqiptv/releases/download/v1.0.0/install.sh | sh
```

> 若 `github.com` 直连不稳定，在交互模式中可选择 `gh-proxy.com` 或 `ghfast.top` 镜像加速；也可以改用仓库 raw 地址（需能访问 `raw.githubusercontent.com`）：
> `uclient-fetch -q --no-check-certificate -O - https://raw.githubusercontent.com/gy520187/cqiptv/openwrt/install.sh | sh`
> 若命令执行后无任何输出，先去掉 `-q` 重跑一次查看网络错误；若已安装 `ca-certificates`，可去掉 `--no-check-certificate`。缺少 `curl` 时脚本会自动 `opkg install curl`。

非交互模式（`sh -s` 传递命令参数，可用环境变量 `GITHUB_MIRROR=gh-proxy|ghfast` 指定镜像）：

```bash
uclient-fetch -q --no-check-certificate -O - https://github.com/gy520187/cqiptv/releases/download/v1.0.0/install.sh | sh -s update      # 更新到最新版
uclient-fetch -q --no-check-certificate -O - https://github.com/gy520187/cqiptv/releases/download/v1.0.0/install.sh | sh -s reinstall   # 强制重装
uclient-fetch -q --no-check-certificate -O - https://github.com/gy520187/cqiptv/releases/download/v1.0.0/install.sh | sh -s uninstall      # 卸载（保留 /etc/cqiptv 数据）
uclient-fetch -q --no-check-certificate -O - https://github.com/gy520187/cqiptv/releases/download/v1.0.0/install.sh | sh -s uninstall-full # 卸载并清除全部数据（配置/M3U/EPG/图标及 UCI 配置）
uclient-fetch -q --no-check-certificate -O - https://github.com/gy520187/cqiptv/releases/download/v1.0.0/install.sh | sh -s status      # 查看状态
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
	option icon_host ''                     # M3U 图标地址，留空自动检测路由器 LAN IP（如 http://192.168.50.2:6061）
	option epg_url ''                       # M3U x-tvg-url，留空用默认
	option epg_workers '2'                  # EPG 并行线程数

config cqiptv 'scheduler'
	option cron '0 4 * * *'                 # 默认 cron（兜底），实际以 Web「定时任务」页配置为准
```

> 定时采集统一在 Web 界面配置：浏览器打开 `http://<路由器IP>:6061` →「定时任务」页设置 cron 与开关，保存后立即生效，无需修改 UCI。定时任务进程随服务常驻，未启用任务时仅空转等待。

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

本分支（`openwrt`）是 OpenWrt 版的独立分支，源码直接位于仓库根目录的
`cqiptv/files/usr/share/cqiptv/` 下（`main.py`、`scheduler.py`、`server.py`、
`iptv/`、`web/`、`tools/`、`config.example.yaml`，`vendor/` 一般无需变动）。
修改后重新 `ipkg-build` 编译，并将生成的 `.ipk` 上传到 GitHub Releases 即可。

> **v1.0.0 起移除固件提取工具**（`download_firmware.py`）。旧版升级/强制重装时，
> 一键脚本会自动清理 `/usr/share/cqiptv/tools/download_firmware.py` 等遗留文件。