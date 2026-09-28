# scripts/fetch_epg.py — 手动拉取单个频道 EPG（容器内运行，只打印与落盘，不写 storage）
# 用法: cd /mnt/sata1-4/iptvcq
#       docker compose exec -T iptv-scheduler python - < scripts/fetch_epg.py 云南卫视
import json
import os
import sys

from iptv.config import load_config
from iptv.logger import setup_logger
from iptv.http_client import HttpClient
from iptv.auth import Authenticator
from iptv.channel import ChannelCollector, build_alias_map
from iptv.channel_info import ChannelInfoParser
from iptv.filter import filter_channels
from iptv.epg import EPGCollector, alt_ids_for
from iptv.utils import normalize_channel_name

keyword = sys.argv[1] if len(sys.argv) > 1 else "云南卫视"

cfg = load_config("config.yaml")
log = setup_logger(cfg)

# 认证拿到 host 与会话 Cookie（EPG 请求挂同一 session）
http = HttpClient(cfg, log)
result = Authenticator(cfg, http, log).login()
if not result:
    sys.exit("认证失败，无法拉取")
host, cookies, user_token, stbid, temp_key = result
log.info(f"认证成功: host={host}")

# 频道列表 → 过滤 → 按关键字匹配（原始名/归一化名都比对）
collector = ChannelCollector(cfg, http, log)
variants_all = collector.flatten(collector.fetch())
channels = filter_channels(variants_all)
log.info(f"频道列表 {len(channels)} 个")

hits = [c for c in channels
        if keyword in c["channelName"]
        or keyword in normalize_channel_name(c["channelName"])]
if not hits:
    sys.exit(f"未找到频道: {keyword}")
hits.sort(key=lambda c: int(c["channelIndex"]))
target = hits[0]
log.info(f"命中 {len(hits)} 个, 取 channelIndex 最小者: "
         f"{target['channelName']} (channelID={target['channelID']}, "
         f"channelIndex={target['channelIndex']})")

# getchannellist 建同名变体备用 ID 映射（高清 ID 无节目时回退，如 云南卫视）
info_body = {
    "conntype": "4",
    "UserToken": user_token,
    "tempKey": temp_key,
    "stbid": stbid,
    "SupportHD": "1",
    "UserID": cfg.user_id,
    "Lang": "1",
}
html = http.post(
    f"http://{host}/EPG/jsp/getchannellistHWCTC.jsp",
    data=info_body,
    referer=f"http://{host}/EPG/jsp/ValidAuthenticationHWCTC.jsp",
    origin=f"http://{host}",
    full_url=True,
)
channel_infos = ChannelInfoParser(log).parse(html) if html else {}
# 备用 ID 映射: channelList 全量变体 + getchannellist（含 4K 变体）取并集
alias_map = build_alias_map(variants_all, channel_infos)
# 4K 频道优先套用基础(高清)频道 ID, 再附同名变体
alt_ids = alt_ids_for(target, alias_map)
if alt_ids:
    log.info(f"备用 ID: {', '.join(alt_ids)}")

# 逐天拉取节目单（含历史 6 天 + 未来 2 天，主 ID 全空自动回退备用 ID）
epg = EPGCollector(cfg, http, log).fetch(target["channelID"], alt_ids)
days = epg["programs"]
total = sum(len(d) for d in days)
log.info(f"拉取完成: {len(days)} 天 / {total} 条节目")
for day in days:
    if day:
        log.info(f"  {day[0].get('beginTimeFormat', '')[:8]}: {len(day):4d} 条  "
                 f"{day[0].get('beginTimeFormat')} ~ {day[-1].get('endTimeFormat')}")

# JSON 落盘到容器 output/（compose 已挂载到宿主机 ./output）
out = {
    "channel": {
        "channelName": target["channelName"],
        "channelNameRaw": target.get("channelNameRaw", ""),
        "channelID": target["channelID"],
        "channelIndex": target["channelIndex"],
    },
    "dates": epg["dates"],
    "programs": days,
}
os.makedirs("output", exist_ok=True)
path = os.path.join("output", f"manual_epg_{target['channelID']}.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"JSON 已写入: 宿主机 ./output/manual_epg_{target['channelID']}.json")
