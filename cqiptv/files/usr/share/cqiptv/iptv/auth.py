# iptv/auth.py
"""
IPTV 认证模块

流程：
  ① 认证入口（GET，302）→ 提取 host
  ② 登录（POST authLoginHWCTC.jsp）→ 提取动态 EncryptToken + userToken
  ③ 生成 Authenticator（明文：{key}${EncryptToken}${UserID}${STBID}${ip}${mac}$$CTC）
  ④ 鉴权（POST ValidAuthenticationHWCTC.jsp，23 字段按原始抓包对齐）
  ⑤ 检查 isSucessed，提取 UserToken + stbid

★ 关键：
  1. 所有请求走 self.http.session，cookies 自动共享给后续频道/EPG 请求
  2. 认证入口 URL = auth_ip 去掉 /EPG/jsp 后 + /EDS/jsp/...
     业务 URL = auth_ip 原样 + 路径（由 http_client.url() 拼接）
"""

import re
import time
from typing import Optional, Tuple
import requests
from urllib.parse import urlparse

from . import constants
from .authenticator import AuthenticatorCrypto
from .utils import mask_secret


class Authenticator:
    def __init__(self, cfg, http, logger):
        self.cfg = cfg
        self.http = http
        self.logger = logger
        self.host = ""           # 认证后得到的真实 host

    # ========== 主流程 ==========
    def login(self) -> Optional[Tuple[str, dict, str, str, str]]:
        """
        完整认证流程
        :return: (host, cookies, user_token, stbid, temp_key) 或 None
        """
        user_id = self.cfg.user_id
        mac = self.cfg.mac
        stb_id = self.cfg.stb_id
        stb_type = self.cfg.stb_type
        stb_version = self.cfg.stb_version
        ip = self.cfg.get("ip") or "173.45.20.200"
        software_version = self.cfg.software_version
        key = self.cfg.key
        user_agent = self.cfg.get("UserAgent") or (
            "Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/534.0 (KHTML, like Gecko)"
        )

        if not user_id:
            self.logger.error("UserID 未配置")
            return None
        if not key:
            self.logger.error("key 未配置")
            return None

        # 认证入口（从配置读，可能带 /EPG/jsp）
        auth_ip = self.cfg.auth_ip or "http://192.0.2.10:33200"
        if not auth_ip.startswith("http"):
            auth_ip = f"http://{auth_ip}"

        # ★ 认证入口 base = auth_ip 去掉 /EPG/jsp
        auth_base = auth_ip.replace("/EPG/jsp", "").rstrip("/")
        self.logger.info(f"认证 base: {auth_base}")

        # 重试 3 次
        for attempt in range(3):
            try:
                # ========== 步骤1: 认证入口 ==========
                # 与原始抓包一致：FCCSupport=1，Referer 指向 epg.itv.cq.cn 入口页
                self.logger.info(f"步骤1: 认证入口 (尝试 {attempt+1}/3)")
                url = f"{auth_base}/EDS/jsp/AuthenticationURL?UserID={user_id}&Action=Login&FCCSupport=1"
                self.logger.info(f"  认证 URL: {url.replace(user_id, mask_secret(user_id))}")

                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,en-US;q=0.8",
                    "User-Agent": user_agent,
                    "Referer": f"{constants.AUTH_PUBLIC}?UserID={user_id}&Action=Login&FCCSupport=1",
                    "X-Requested-With": "com.android.smart.terminal.iptv",
                }
                # ★ 用 self.http.session，cookies 自动管理
                r = self.http.session.get(url, headers=headers, timeout=10, allow_redirects=False)
                r.raise_for_status()

                location = r.headers.get("Location", "")
                self.host = urlparse(location).netloc or urlparse(auth_base).netloc
                self.logger.info(f"  host: {self.host}")

                if not self.host:
                    raise ValueError("无法解析 host")

                # ========== 步骤2: 登录 ==========
                self.logger.info("步骤2: 登录")
                auth_url = f"http://{self.host}/EPG/jsp/authLoginHWCTC.jsp"
                auth_headers = {
                    "User-Agent": user_agent,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept-Language": "zh-CN,en-US;q=0.8",
                    "Origin": f"http://{self.host}",
                    "Referer": f"http://{self.host}/EPG/jsp/AuthenticationURL?UserID={user_id}&Action=Login&FCCSupport=1",
                    "X-Requested-With": "com.android.smart.terminal.iptv",
                }
                ar = self.http.session.post(       # ★ 用 self.http.session
                    auth_url,
                    headers=auth_headers,
                    data={"UserID": user_id, "VIP": ""},
                    timeout=10,
                )
                ar.raise_for_status()
                self.logger.debug(f"  登录响应: {ar.text[:300]}")

                # 提取 EncryptToken
                m = re.search(r'var\s+EncryptToken\s*=\s*"([^"]+)"', ar.text)
                if not m:
                    raise ValueError("无法找到 EncryptToken")
                encrypt_token = m.group(1)
                self.logger.info(f"  EncryptToken: {mask_secret(encrypt_token)}")

                # 提取 userToken
                m = re.search(r'document\.authform\.userToken\.value\s*=\s*"([^"]+)"', ar.text)
                if not m:
                    raise ValueError("无法找到 userToken")
                user_token = m.group(1)
                self.logger.info(f"  userToken: {mask_secret(user_token)}")

                # ========== 步骤3: 生成 Authenticator ==========
                self.logger.info("步骤3: 生成 Authenticator")
                pc = AuthenticatorCrypto(key)

                # ★ 照抄可用脚本：明文 = {key}$EncryptToken$UserID$STBID$ip$mac$$CTC
                auth_str = f"{key}${encrypt_token}${user_id}${stb_id}${ip}${mac}$$CTC"
                self.logger.info(f"  明文: {len(auth_str)} 字符（内容已脱敏）")

                authenticator = pc.encrypt(auth_str)
                self.logger.info(f"  密文: {authenticator[:32]}...")

                # ========== 步骤4: 鉴权（23 字段，与原始抓包逐项对齐） ==========
                self.logger.info("步骤4: 鉴权")
                valid_url = f"http://{self.host}/EPG/jsp/ValidAuthenticationHWCTC.jsp"
                valid_headers = {
                    "User-Agent": user_agent,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept-Language": "zh-CN,en-US;q=0.8",
                    "Origin": f"http://{self.host}",
                    "Referer": f"http://{self.host}/EPG/jsp/authLoginHWCTC.jsp",
                }
                valid_data = {
                    # 机顶盒表单先编码 @→%40，浏览器再编码 %→%25，线上为双重编码，requests 侧需预置 %40
                    "UserID": user_id.replace("@", "%40"),
                    "Lang": "1",
                    "SupportHD": "1",
                    "NetUserID": user_id,
                    "Authenticator": authenticator,
                    "STBType": stb_type,
                    "STBVersion": stb_version,
                    "conntype": "4",
                    "STBID": stb_id,
                    "templateName": constants.TEMPLATE_NAME,
                    "areaId": constants.AREA_ID,
                    "userToken": user_token,
                    "userGroupId": constants.USER_GROUP,
                    "productPackageId": constants.PRODUCT_PACKAGE_ID,
                    "mac": mac,
                    "UserField": constants.USER_FIELD,
                    "SoftwareVersion": software_version,
                    "IsSmartStb": constants.IS_SMART_STB,
                    "desktopId": "",
                    "stbmaker": "",
                    "XMPPCapability": constants.XMPP_CAPABILITY,
                    "ChipID": "",
                    "VIP": "",
                }
                vr = self.http.session.post(       # ★ 用 self.http.session
                    valid_url,
                    headers=valid_headers,
                    data=valid_data,
                    timeout=10,
                )
                vr.raise_for_status()

                # ★ 检查 isSucessed
                if "isSucessed = true" in vr.text:
                    self.logger.info("  ✅ isSucessed = true")
                elif "isSucessed = false" in vr.text:
                    self.logger.error("  ❌ isSucessed = false")
                    m_err = re.search(r'action="(ComInfoDisplay[^"]+)"', vr.text)
                    if m_err:
                        self.logger.error(f"  错误页: {m_err.group(1)}")
                    # 认证失败，重试
                    if attempt < 2:
                        time.sleep(5)
                    continue

                # ========== 步骤5: 提取 UserToken 和 stbid ==========
                cookies = self.http.session.cookies.get_dict()   # ★ 从 session 拿
                self.logger.info(f"  JSESSIONID: {mask_secret(cookies.get('JSESSIONID'))}")
                self.logger.info(f"  Cookie: { {k: mask_secret(v) for k, v in cookies.items()} }")

                # 提取 UserToken
                m = re.search(r'name="UserToken"\s*value="([^"]+)"', vr.text)
                resp_user_token = m.group(1) if m else None

                # 提取 stbid（短格式，如 990060）
                m = re.search(r'name="stbid"\s*value="([^"]+)"', vr.text)
                resp_stbid = m.group(1) if m else None

                # 提取 tempKey（getchannellistHWCTC 等后续请求需要）
                # 原始抓包中 tempKey 由机顶盒中间件 CTCGetConfig('identityEncode') 填入，
                # HTML 模板中恒为空值，纯软件环境无法复现计算，按空值提交（服务端不强校验）
                m = re.search(r'tempKey\s*[=:]\s*["\']?([0-9A-Fa-f]{16,64})', vr.text)
                temp_key = m.group(1) if m else ""
                if not temp_key:
                    m = re.search(r'tempKey\s*[=:]\s*["\']?([0-9A-Fa-f]{16,64})', ar.text)
                    temp_key = m.group(1) if m else ""
                self.logger.info(f"  tempKey: {mask_secret(temp_key) or '（响应中未找到，按空值提交）'}")

                if not resp_user_token or not resp_stbid:
                    self.logger.error("无法从 HTML 中提取 UserToken 或 stbid")
                    self.logger.debug(f"  响应前 500 字: {vr.text[:500]}")
                    return None

                self.logger.info(f"  UserToken: {mask_secret(resp_user_token)}")
                self.logger.info(f"  stbid: {mask_secret(resp_stbid)}")

                # ★ 验证 session 里有 JSESSIONID
                if not cookies.get("JSESSIONID"):
                    self.logger.warning("  ⚠️ session 中无 JSESSIONID，尝试从响应头提取")
                    m_cookie = re.search(r'JSESSIONID="?([^";]+)"?', vr.headers.get("Set-Cookie", ""))
                    if m_cookie:
                        self.http.session.cookies.set("JSESSIONID", m_cookie.group(1))
                        self.logger.info(f"  从响应头提取: {mask_secret(m_cookie.group(1))}")

                return self.host, cookies, resp_user_token, resp_stbid, temp_key

            except requests.exceptions.RequestException as e:
                self.logger.error(f"请求失败: {e}")
                if attempt < 2:
                    self.logger.info("等待 5 秒后重试...")
                    time.sleep(5)
            except ValueError as e:
                self.logger.error(f"解析失败: {e}")
                if attempt < 2:
                    time.sleep(5)

        self.logger.error("认证失败，已达最大重试次数")
        return None

    def get_host(self) -> str:
        """获取认证后的 host（供后续请求用）"""
        return self.host or urlparse(self.cfg.auth_ip or "").netloc