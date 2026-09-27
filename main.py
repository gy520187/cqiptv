# main.py
import sys
import traceback
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from iptv.http_client import HttpClient
from iptv.auth import Authenticator
from iptv.key_manager import KeyManager
from iptv.channel import ChannelCollector
from iptv.channel_info import ChannelInfoParser
from iptv.mediacode import MediacodeCollector
from iptv.epg import EPGCollector
from iptv.filter import filter_channels
from iptv.xmltv import XMLTVGenerator
from iptv.m3u_normalized import NormalizedM3UGenerator
from iptv.icon import IconHandler
from iptv.storage import Storage


def collect():
    logger = None
    try:
        cfg = load_config("config.yaml")
        logger = setup_logger(cfg)
        logger.info("=" * 60)
        logger.info("IPTV 采集开始")

        if cfg.is_first_run():
            logger.error("配置不完整，请先在 Web 界面配置")
            sys.exit(1)

        # ========== 密钥 ==========
        km = KeyManager(cfg, logger)
        key = km.get_or_crack()
        if key:
            for k, v in km.decrypt_info(key).items():
                logger.info(f"  {k}: {v}")

        # ========== HTTP ==========
        http = HttpClient(cfg, logger)

        # ========== 认证 ==========
        auth = Authenticator(cfg, http, logger)
        result = auth.login()
        if not result:
            logger.error("认证失败，退出")
            sys.exit(1)
        host, cookies, user_token, stbid = result
        logger.info(f"认证成功: host={host}")

        # ========== 频道列表 ==========
        ch_collector = ChannelCollector(cfg, http, logger)
        raw = ch_collector.fetch()
        if not raw:
            logger.error("频道列表为空")
            sys.exit(1)
        channels = ch_collector.flatten(raw)
        logger.info(f"扁平化 {len(channels)}")

        # ========== 过滤 ==========
        channels = filter_channels(channels)
        logger.info(f"过滤后 {len(channels)}")

        # ========== 媒体编码 ==========
        mediacodes = MediacodeCollector(cfg, http, logger).fetch()
        for ch in channels:
            ch["mediacode"] = mediacodes.get(str(ch["channelIndex"]), "")

        # ========== 组播地址 ==========
        channel_infos = {}
        referer = http.url("/diyiyingshi/en/channel/channelCore.jsp")
        html = http.get(constants.PATH_CHANNEL_INFO, referer=referer)
        if html:
            channel_infos = ChannelInfoParser(logger).parse(html)
        logger.info(f"组播地址: {len(channel_infos)} 个")

        # ========== 节目单 ==========
        epgs = EPGCollector(cfg, http, logger).fetch_all(channels)
        logger.info(f"节目单: {len(epgs)} 个频道")

        # ========== 图标 ==========
        logger.info(">>> 开始处理图标")
        IconHandler(cfg, logger).ensure_all(channels, force=constants.ICON_FORCE)
        logger.info(">>> 图标处理完成")

        # ========== 输出 ==========
        logger.info(">>> 1. Storage.save 开始")
        Storage(cfg, logger).save(channels, epgs)
        logger.info(">>> 1. Storage.save 完成")

        logger.info(">>> 2. XMLTVGenerator.save 开始")
        XMLTVGenerator(cfg, logger).save(channels, epgs)
        logger.info(">>> 2. XMLTVGenerator.save 完成")

        logger.info(">>> 3. M3UGenerator.save 开始")
        NormalizedM3UGenerator(cfg, logger).save(channels, channel_infos)
        logger.info(">>> 3. M3UGenerator.save 完成")

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


if __name__ == "__main__":
    collect()