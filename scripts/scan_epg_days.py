# scripts/scan_epg_days.py — 扫描运营商 EPG 日期窗口（诊断用）
# 在能访问运营商网络的部署环境运行（重庆电信内网）：
#   docker compose exec -T iptv-scheduler python - < scripts/scan_epg_days.py
#   或: python scripts/scan_epg_days.py [频道关键字] [起始dateIndex] [结束dateIndex]
# 输出每个 dateIndex 的节目条数、首末时间与 data[0] 日期窗口，
# 据此判断运营商实际支持的历史/未来节目天数。
import json
import logging
import sys
import time

from iptv.config import load_config
from iptv.http_client import HttpClient
from iptv.auth import Authenticator
from iptv import constants

keyword = sys.argv[1] if len(sys.argv) > 1 else "CCTV-1"
scan_start = int(sys.argv[2]) if len(sys.argv) > 2 else -30
scan_end = int(sys.argv[3]) if len(sys.argv) > 3 else 30

cfg = load_config("config.yaml")
log = logging.getLogger("scan_epg_days")
log.setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)

http = HttpClient(cfg, log)
r = Authenticator(cfg, http, log).login()
if not r:
    sys.exit("认证失败，无法扫描")
referer = http.url("/diyiyingshi/en/channel/channelPlayingList.html")

from iptv.channel import ChannelCollector
from iptv.utils import normalize_channel_name
from iptv.filter import filter_channels

collector = ChannelCollector(cfg, http, log)
variants_all = collector.flatten(collector.fetch())
channels = filter_channels(variants_all)
hits = [c for c in channels
        if keyword in c["channelName"] or keyword in normalize_channel_name(c["channelName"])]
if not hits:
    sys.exit(f"未找到频道: {keyword}")
target = sorted(hits, key=lambda c: int(c["channelIndex"]))[0]
cid = target["channelID"]
print(f"扫描频道: {target['channelName']} channelID={cid}")
print(f"扫描 dateIndex 范围: {scan_start}..{scan_end}")

def req(di, dsize=2):
    params = {
        "channelId": cid,
        "dateIndex": di,
        "dateSize": dsize,
        "tVodNumPerPage": constants.EPG_PER_DAY,
    }
    return http.get(constants.PATH_EPG, params, referer)

def parse(text):
    if not text:
        return None, []
    try:
        data = json.loads(text)
    except Exception:
        return None, []
    if not isinstance(data, list) or len(data) < 2:
        return None, []
    info = data[0] if isinstance(data[0], dict) else {}
    pages = data[1].get("data", []) if isinstance(data[1], dict) else []
    progs = [p for g in pages if isinstance(g, list) for p in g if isinstance(p, dict)]
    return info, progs

active = []
for di in range(scan_start, scan_end + 1):
    info, progs = parse(req(di))
    win = info.get("data") if info else None
    if progs:
        first = progs[0].get("beginTimeFormat", "?")
        last = progs[-1].get("endTimeFormat", "?")
        active.append(di)
        win_txt = ""
        if isinstance(win, list) and win:
            win_txt = f"  窗口[{len(win)}天] {win[0]}~{win[-1]}"
        print(f"  dateIndex={di:3d}: {len(progs):3d} 条  {first} ~ {last}{win_txt}")
    else:
        print(f"  dateIndex={di:3d}:   0 条（无节目数据）")
    time.sleep(0.3)

if active:
    print(f"\n结论: 该频道在 dateIndex {min(active)}..{max(active)} 有节目数据"
          f"（历史 {abs(min(active))} 天 / 未来 {max(active)} 天）")
else:
    print("\n结论: 扫描范围内未找到任何节目数据")