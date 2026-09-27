# iptv/constants.py
"""
写死的配置（不需要在 config.yaml 中修改）
"""

# ========== 服务器地址 ==========
DEFAULT_EPG_BASE = "http://172.23.88.159:33200/EPG/jsp"
AUTH_PUBLIC = "http://epg.itv.cq.cn:8080/EDS/jsp/AuthenticationURL"

# ========== 路径 ==========
PATH_CHANNEL_LIST = "/diyiyingshi/en/utilsData/channelList.jsp"
PATH_EPG = "/diyiyingshi/en/utilsData/tVodProgramList.jsp"
PATH_MEDIACODE = "/diyiyingshi/en/utilsData/channelMediacode.js"
PATH_CHANNEL_INFO = "/getchannellistHWCTC.jsp"
PATH_AUTH_LOGIN = "/authLoginHWCTC.jsp"

# ========== 采集参数 ==========
DATE_SIZE = 8
PER_PAGE = 6
INTERVAL = 0.1
TIMEOUT = 10
RETRY = 3
MAX_CHANNELS = 0

# ========== 模板/用户组 ==========
TEMPLATE_NAME = "meilixinnongcunhangyebanitvfenzu"
USER_GROUP = "1037"
AREA_ID = "10006"
IS_COUNTRY_CHANNEL = 1

# ========== 过滤规则 ==========
EXCLUDE_CHANNELS = {"江苏晚会4K", "江苏晚会4k"}

# ========== 图标 ==========
FANMINGMING_BASE = "https://live.fanmingming.cn/tv/{name}.png"
ICON_DIR = "data/icon"
ICON_HOST = "http://iptv.20221122.xyz:6000"   # 改成你的服务器地址
ICON_FORCE = False

# ========== 输出 ==========
OUTPUT_DIR = "output"
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
WEB_PORT = 6000

# ========== 定时任务 ==========
SCHEDULER_ENABLED = True
SCHEDULER_CRON = "0 4 * * *"

# ========== 日志 ==========
LOG_LEVEL = "INFO"
LOG_DIR = "log"
LOG_FILE = "iptv.log"