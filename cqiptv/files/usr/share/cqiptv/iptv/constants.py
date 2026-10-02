# iptv/constants.py
"""
写死的配置（不需要在 config.yaml 中修改）

部署相关的两项（ICON_HOST / WEB_PORT）可用环境变量覆盖，见 .env.example
"""
import os

# 统一使用北京时间；日志格式化见 logger.py（不依赖 tzset，兼容 OpenWrt Python）
os.environ.setdefault("TZ", "Asia/Shanghai")

# ========== 服务器地址 ==========
DEFAULT_EPG_BASE = "http://192.0.2.10:33200/EPG/jsp"
AUTH_PUBLIC = "http://epg.itv.cq.cn:8080/EDS/jsp/AuthenticationURL"

# ========== 路径 ==========
# OpenWrt 版由 init.d 通过环境变量指定绝对基础目录（/etc/cqiptv），
# 所有数据路径基于它拼接，不依赖进程 cwd（部分固件 procd 的 cwd 参数不生效，
# 否则相对路径会落到 /app 下）。Docker/本地版不设置时保持相对路径行为不变。
BASE_DIR = os.getenv("CQIPTV_BASE_DIR") or ""
PATH_CHANNEL_LIST = "/diyiyingshi/en/utilsData/channelList.jsp"
PATH_EPG = "/diyiyingshi/en/utilsData/tVodProgramList.jsp"
PATH_MEDIACODE = "/diyiyingshi/en/utilsData/channelMediacode.js"
PATH_CHANNEL_INFO = "/getchannellistHWCTC.jsp"
PATH_AUTH_LOGIN = "/authLoginHWCTC.jsp"

# ========== 采集参数 ==========
# 原始抓包证实：运营商 EPG 播放器日期窗口为 dateIndex -6..+1（6 天历史回看 + 当天 + 明天）
DATE_SIZE = 2        # EPG 采集天数（dateIndex 0..1，当天+明天，运营商接口一次只回一天）
EPG_HISTORY_DAYS = 6 # 历史节目单天数（dateIndex -6..-1），供播放器回看 catchup 定位过去节目
EPG_DATE_SIZE = 2    # 请求参数 dateSize，与原始抓包的回看节目单请求一致
EPG_PER_DAY = 999    # 单页拉全天节目（999 足够容纳一天的全部节目）
INTERVAL = 0.1
TIMEOUT = 10
RETRY = 3
MAX_CHANNELS = 0
# EPG 并发采集线程数（环境变量可覆盖，0/1 表示串行）
EPG_WORKERS = int(os.getenv("EPG_WORKERS") or "4")
# EPG 按天缓存目录：每频道每天一个文件，增量采集时先检查本地缓存，避免重复请求
EPG_CACHE_DIR = os.path.join(BASE_DIR, "data/epg_cache")

# ========== 模板/用户组（与原始抓包对齐） ==========
TEMPLATE_NAME = "meilixinnongcunhangyebanitvfenzu"
USER_GROUP = "1037"
AREA_ID = "CD0"
PRODUCT_PACKAGE_ID = "-1"
USER_FIELD = "2"
XMPP_CAPABILITY = "1"
IS_SMART_STB = "0"
IS_COUNTRY_CHANNEL = 1

# ========== 过滤规则 ==========
# 江苏晚会4K: 临时晚会频道; 重庆卫视频道: 重庆卫视的 SD 重复频道
EXCLUDE_CHANNELS = {"江苏晚会4K", "江苏晚会4k", "重庆卫视频道"}

# ========== 图标 ==========
# 自动检测本机局域网 IP（OpenWrt 优先 br-lan），未检测到时回退占位地址
def _detect_lan_ip():
    try:
        import subprocess
        for dev in ("br-lan", "eth0", "eth0.2", "en0", "wlan0"):
            try:
                out = subprocess.check_output(
                    ["ip", "-4", "-o", "addr", "show", "dev", dev],
                    stderr=subprocess.DEVNULL, timeout=3,
                ).decode("utf-8", "ignore")
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 4 and "/" in parts[3]:
                        return parts[3].split("/")[0]
            except Exception:
                continue
    except Exception:
        pass
    return ""

# 注意: icon.py 中实际使用 gh-proxy 加速的 FANMINGMING_BASE，此路径常量仅供部署参考
ICON_DIR = os.path.join(BASE_DIR, "data/icon")
_DEFAULT_WEB_PORT = os.getenv("WEB_PORT") or "6061"
_lan_ip = _detect_lan_ip()
ICON_HOST = os.getenv("ICON_HOST") or (f"http://{_lan_ip}:{_DEFAULT_WEB_PORT}" if _lan_ip else "http://your-server:6061")   # M3U 引用的图标地址；自动使用本机 LAN IP，播放器可达
EPG_URL = os.getenv("EPG_URL") or f"{ICON_HOST}/epg.xml.gz"     # M3U 头部 x-tvg-url 指向的节目单地址，留空默认 ICON_HOST/epg.xml.gz（gzip 版体积约为 xml 的 1/10）
ICON_FORCE = False

# 外部 EPG 补充源：仅用于运营商无节目数据的频道（运营商数据优先）。
# 支持多个 URL 用逗号分隔，按顺序加载，先到先得；留空禁用
EXTERNAL_EPG_URL = os.getenv(
    "EXTERNAL_EPG_URL",
    "https://raw.githubusercontent.com/kuke31/xmlgz/main/all.xml.gz,"
    "http://epg.51zmt.top:8000/e.xml.gz",
)
EXTERNAL_EPG_TIMEOUT = 60  # 单个外部 EPG 源下载超时（秒）

# ========== 输出 ==========
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_FORMAT = "both"
OUTPUT_PRETTY = True
R2H_SEEK_OFFSET = 28800

# ========== 破解参数 ==========
CRACK_START = 0
CRACK_END = 100000000
CRACK_MAX_FOUND = 5
CRACK_WORKERS = 8
CRACK_WRITE_BACK = True

# ========== Web ==========
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.getenv("WEB_PORT") or "6061")

# ========== 定时任务 ==========
# 支持环境变量覆盖（OpenWrt 打包时由 UCI 配置导出）
SCHEDULER_ENABLED = (os.getenv("SCHEDULER_ENABLED", "1").lower()
                     in ("1", "true", "yes", "on"))
SCHEDULER_CRON = os.getenv("SCHEDULER_CRON", "0 4 * * *")
# 定时任务配置变更标记：Web 保存定时任务配置后写入，scheduler 检测到后重新加载配置
SCHEDULER_RELOAD_FLAG = os.path.join(BASE_DIR, "data/scheduler_reload.flag")

# ========== 日志 ==========
LOG_LEVEL = "INFO"
LOG_DIR = os.path.join(BASE_DIR, "log")
LOG_FILE = "iptv.log"