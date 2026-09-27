# scripts/debug_epg_raw.py — 诊断单频道 EPG 原始响应（对比控制频道 + 两种请求形态）
# 用法: docker compose exec -T iptv-scheduler python - < scripts/debug_epg_raw.py
import sys

from iptv.config import load_config
from iptv.logger import setup_logger
from iptv.http_client import HttpClient
from iptv.auth import Authenticator
from iptv import constants

cfg = load_config("config.yaml")
log = setup_logger(cfg)
http = HttpClient(cfg, log)
r = Authenticator(cfg, http, log).login()
if not r:
    sys.exit("认证失败")
log.info(f"认证成功 host={r[0]}")
referer = http.url("/diyiyingshi/en/channel/channelPlayingList.html")

def req(cid, di, extra=None):
    params = {"channelId": cid, "dateIndex": di,
              "dateSize": constants.EPG_DATE_SIZE,
              "tVodNumPerPage": constants.EPG_PER_DAY}
    if extra:
        params.update(extra)
    return http.get(constants.PATH_EPG, params, referer)

# 目标: 云南卫视(高清)/云南卫视(SD); 控制: CCTV-1综合(高清)（全量采集中有数据）
targets = [("云南卫视(高清)", "642905769"), ("云南卫视.(SD)", "1672"),
           ("CCTV-1综合(高清)", "1491")]
for name, cid in targets:
    for di in (0, 1):
        print(f"\n===== {name} channelId={cid} dateIndex={di} 回看形态 =====")
        print((req(cid, di) or "None")[:600])
    print(f"\n----- {name} channelId={cid} dateIndex=0 核心流形态(columnId+dateSize=8+每页6) -----")
    print((req(cid, 0, {"columnId": "", "dateSize": 8, "tVodNumPerPage": 6}) or "None")[:600])
