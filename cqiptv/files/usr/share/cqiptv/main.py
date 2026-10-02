# main.py
import os
import argparse
import sys
import traceback
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from iptv.http_client import HttpClient
from iptv.auth import Authenticator
from iptv.key_manager import KeyManager
from iptv.channel import ChannelCollector, merge_missing_channels, build_alias_map
from iptv.channel_info import ChannelInfoParser
from iptv.mediacode import MediacodeCollector
from iptv.epg import EPGCollector
from iptv.filter import filter_channels
from iptv.xmltv import XMLTVGenerator
from iptv.m3u_normalized import NormalizedM3UGenerator
from iptv.icon import IconHandler
from iptv.storage import Storage
from iptv.utils import mask_secret


def _acquire_collect_lock(logger):
    """跨进程采集互斥锁：Web 手动采集与 scheduler 定时采集是独立进程，
    不加锁会同时请求运营商并竞争写 output 文件。非阻塞获取，失败说明另一进程正在采集。"""
    os.makedirs(constants.OUTPUT_DIR, exist_ok=True)
    lock_path = os.path.join(constants.OUTPUT_DIR, ".collect.lock")
    f = open(lock_path, "w", encoding="utf-8")
    try:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None
    except ImportError:
        # 无 fcntl 平台（如 Windows）退化为单进程占位，不互斥
        return f


def _release_collect_lock(lock):
    try:
        import fcntl
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    finally:
        lock.close()


def collect(allow_crack=True, force_refresh=False):
    logger = None
    lock = None
    try:
        cfg = load_config()
        logger = setup_logger(cfg)
        logger.info("=" * 60)
        logger.info("IPTV 采集开始")

        lock = _acquire_collect_lock(logger)
        if lock is None:
            logger.info("已有采集任务在运行，跳过本次采集")
            return

        if cfg.is_first_run():
            logger.error("配置不完整，请先在 Web 界面配置")
            sys.exit(1)

        # ========== 密钥 ==========
        km = KeyManager(cfg, logger)
        key = km.get_or_crack(allow_crack=allow_crack)
        if key:
            for k, v in km.decrypt_info(key).items():
                # 解密信息含 token/user_id/stb_id/mac 等凭据，公网日志可见，必须脱敏
                logger.info(f"  {k}: {mask_secret(v)}")

        # ========== HTTP ==========
        http = HttpClient(cfg, logger)

        # ========== 认证 ==========
        auth = Authenticator(cfg, http, logger)
        result = auth.login()
        if not result:
            logger.error("认证失败，退出")
            sys.exit(1)
        host, cookies, user_token, stbid, temp_key = result
        logger.info(f"认证成功: host={host}")

        # ========== 频道列表 ==========
        ch_collector = ChannelCollector(cfg, http, logger)
        raw = ch_collector.fetch()
        if not raw:
            logger.error("频道列表为空")
            sys.exit(1)
        channels = ch_collector.flatten(raw)
        logger.info(f"扁平化 {len(channels)}")
        # 全量变体列表（含稍后被去重的 SD/标清变体），供 EPG 备用 ID 映射使用
        variants_all = channels

        # ========== 过滤 ==========
        channels = filter_channels(channels)
        logger.info(f"过滤后 {len(channels)}")

        # ========== 媒体编码 ==========
        mediacodes = MediacodeCollector(cfg, http, logger).fetch()
        for ch in channels:
            ch["mediacode"] = mediacodes.get(str(ch["channelIndex"]), "")

        # ========== 组播地址 ==========
        # 照抄机顶盒原始抓包: POST getchannellistHWCTC.jsp, 携带认证凭据
        channel_infos = {}
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
        if html:
            channel_infos = ChannelInfoParser(logger).parse(html)
        logger.info(f"组播地址: {len(channel_infos)} 个")

        # 4K 频道仅在 getchannellist 下发（channelList.jsp 无）；运营商上新频道时
        # channelList 也可能滞后。注入缺失的有组播地址频道，使其参与后续
        # EPG 采集/图标/输出，M3U 带完整组播与回看地址
        channels = merge_missing_channels(channels, channel_infos, logger)

        # ========== 节目单 ==========
        # 同名变体备用 ID 映射: 高清 ID 在 tVod 无节目时回退 SD/其他变体 ID
        alias_map = build_alias_map(variants_all, channel_infos)
        epgs = EPGCollector(cfg, http, logger).fetch_all(channels, alias_map, force=force_refresh)
        logger.info(f"节目单: {len(epgs)} 个频道")

        # ========== 外部 EPG 补充 ==========
        # 运营商数据优先：仅对无节目数据的频道，用第三方 EPG 补充
        if constants.EXTERNAL_EPG_URL:
            from iptv.external_epg import ExternalEPG
            ext = ExternalEPG(cfg, logger)
            if ext.load():
                filled = 0
                for ch in channels:
                    if not isinstance(ch, dict):
                        continue
                    epg = epgs.get(ch.get("channelID"), {})
                    if epg and epg.get("programs"):
                        continue
                    progs = ext.get_programs(ch.get("channelName", ""))
                    if progs:
                        epgs[ch.get("channelID")] = {"programs": [progs]}
                        filled += 1
                logger.info(f"外部 EPG 补充: {filled} 个频道")

        # ========== 图标 ==========
        logger.info(">>> 开始处理图标")
        IconHandler(cfg, logger).ensure_all(channels, force=constants.ICON_FORCE)
        logger.info(">>> 图标处理完成")

        # ========== 输出 ==========
        logger.info(">>> 1. Storage.save 开始")
        # 组播/时移地址并入频道数据，供 Web 界面展示 RTSP/RTP 链接
        for ch in channels:
            if not ch or not isinstance(ch, dict):
                continue
            info = channel_infos.get(ch.get("channelID")) or {}
            if isinstance(info, dict):
                ch.setdefault("channel_url", info.get("channel_url", ""))
                ch.setdefault("timeshift_url", info.get("timeshift_url", ""))
                ch.setdefault("fcc_ip", info.get("fcc_ip", ""))
                ch.setdefault("fcc_port", info.get("fcc_port", ""))
        Storage(cfg, logger).save(channels, epgs)
        logger.info(">>> 1. Storage.save 完成")

        logger.info(">>> 2. XMLTVGenerator.save 开始")
        XMLTVGenerator(cfg, logger).save(channels, epgs)
        logger.info(">>> 2. XMLTVGenerator.save 完成")

        logger.info(">>> 3. M3UGenerator.save 开始")
        p = NormalizedM3UGenerator(cfg, logger).save(channels, channel_infos)
        logger.info(f">>> 3. M3UGenerator.save {'完成' if p else '失败'}")

        logger.info("=" * 60)
        logger.info("采集完成")
        logger.info("=" * 60)

    except Exception as e:
        if logger:
            logger.error(f"采集失败: {e}")
            logger.error("堆栈信息:\n" + traceback.format_exc())
        else:
            print(f"采集失败: {e}")
            traceback.print_exc()
        raise
    finally:
        # 无论正常完成、异常还是 sys.exit，都释放互斥锁
        if lock is not None:
            _release_collect_lock(lock)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IPTV 采集工具")
    parser.add_argument(
        "--crack", action="store_true",
        help="key 缺失或失效时自动暴力破解（8 进程，可能耗时数小时）",
    )
    parser.add_argument(
        "--refresh-epg", action="store_true",
        help="强制全量刷新 EPG，忽略本地缓存重新请求全部日期",
    )
    args = parser.parse_args()
    collect(allow_crack=args.crack, force_refresh=args.refresh_epg)