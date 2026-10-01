#!/usr/bin/env python3
"""使用运营商下发的地址下载 IPTV 盒子固件。

流程（基于真实抓包还原）：
  1. GET http://172.5.129.158:8080/EDS/jsp/upgrade.jsp?<设备参数>  -> 302
  2. 跟随 Location 到 http://172.5.129.207:33500/UPGRADE/jsp/upgrade.jsp -> config.txt（固件清单）
  3. 解析 [FIRMWARE-FULL] 段的 FileName
  4. 下载 http://172.5.129.207:33500/UPGRADE/<FileName>

需要在重庆电信网络内运行（172.x 为运营商内网地址，公网不可达）。

用法：
  python3 tools/download_firmware.py
  python3 tools/download_firmware.py --config /etc/cqiptv/config.yaml
  python3 tools/download_firmware.py --user xxx@itv --mac 28:A6:... --stbid 0010... --type EC6108V9U_pub_cqydx --ver 19.2.0-LCQD15.B011
"""

import argparse
import subprocess
import tempfile
import os
import re
import sys
import gzip
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

PUBLIC_UPGRADE = "http://172.5.129.158:8080/EDS/jsp/upgrade.jsp"
UPGRADE_BASE = "http://172.5.129.207:33500/UPGRADE"

# 固件文件可能的存放目录（按优先级尝试）
DOWNLOAD_PATHS = [
    "/UPGRADE/{f}",
    "/upgrade/{f}",
    "/upgradefile/{f}",
    "/firmware/{f}",
]

USER_AGENT = "Dalvik/1.6.0 (Linux; U; Android 4.4.2; EC6108V9U_pub_cqydx Build/KOT49H)"


def mask_secret(s):
    s = str(s or "")
    if len(s) <= 6:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def load_config(path):
    """极简 YAML 键值解析（不依赖 pyyaml/ruamel）。"""
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, _, val = line.partition(":")
                data[key.strip()] = val.strip().strip("'\"")
    except OSError as e:
        print(f"读取配置失败: {e}")
    return data


def parse_config_txt(text):
    """解析 config.txt（INI 风格），返回 {section: {key: value}}。"""
    sections = {}
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            cur = m.group(1)
            sections[cur] = {}
            continue
        if cur and "=" in line:
            k, _, v = line.partition("=")
            sections[cur][k.strip()] = v.strip()
    return sections


def http_get(url, data=None, timeout=15):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    cmd = [
        "curl", "-sS", "--max-time", str(timeout),
        "-D", "-", "-o", tmp.name,
        "-H", "User-Agent: " + USER_AGENT,
        "-H", "Content-Type: text/plain; charset=utf-8",
    ]
    if data is not None:
        cmd += ["-d", data if isinstance(data, str) else data.decode("latin-1")]
    cmd.append(url)
    try:
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
        except subprocess.TimeoutExpired:
            raise URLError(f"请求超时: {url}")
        except FileNotFoundError:
            raise URLError("未找到 curl，请先安装 curl")
        head_bytes = p.stdout
        with open(tmp.name, "rb") as f:
            body = f.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    lines = head_bytes.split(b"\r\n")
    if not lines or b"HTTP/" not in lines[0]:
        lines = head_bytes.split(b"\n")
    if not lines or b"HTTP/" not in lines[0]:
        raise URLError(f"curl 未返回有效响应头: {head_bytes[:200]!r}")
    code = int(lines[0].split(b" ", 2)[1])
    msg = lines[0].split(b" ", 2)[2].decode("latin-1", "replace")
    headers = {}
    for line in lines[1:]:
        if b":" in line:
            k, _, v = line.partition(b":")
            headers[k.strip().decode("latin-1")] = v.strip().decode("latin-1")
    if code in (301, 302, 303, 307, 308):
        loc = headers.get("Location")
        if loc:
            return urllib.parse.urljoin(url, loc), headers, body
        return url, headers, body
    if code >= 400:
        raise HTTPError(url, code, msg, headers, None)
    return url, headers, body

def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    urllib.request.install_opener(opener)
    ap = argparse.ArgumentParser(description="下载重庆电信 IPTV 盒子固件")
    ap.add_argument("--config", default="config.yaml", help="cqiptv config.yaml 路径")
    ap.add_argument("--user", help="UserID（如 i5207379189@itv）")
    ap.add_argument("--mac", help="机顶盒 MAC（如 28:A6:DB:6F:D2:9E）")
    ap.add_argument("--stbid", help="STBID（32 位十六进制）")
    ap.add_argument("--type", help="STBType / HardwareVersion（如 EC6108V9U_pub_cqydx）")
    ap.add_argument("--ver", help="软件版本（如 19.2.0-LCQD15.B011）")
    ap.add_argument("--section", default="FIRMWARE-FULL", help="固件段，默认 FIRMWARE-FULL（全量）")
    ap.add_argument("--outdir", default=".", help="固件保存目录")
    ap.add_argument("--checksum", default="21270", help="公网入口 CHECKSUM（抓包值，默认 21270）")
    ap.add_argument("--checksum-in", default="21608", help="内网升级服务器 CHECKSUM（抓包值，默认 21608）")
    args = ap.parse_args()

    cfg = {}
    if os.path.exists(args.config):
        cfg = load_config(args.config)
    elif args.config == "config.yaml":
        alt = "/etc/cqiptv/config.yaml"
        if os.path.exists(alt):
            print(f"当前目录无 config.yaml，使用 {alt}")
            cfg = load_config(alt)
    else:
        print(f"配置 {args.config} 不存在，仅使用命令行参数")
    user_id = args.user or cfg.get("UserID") or os.environ.get("USER")
    mac = args.mac or cfg.get("mac") or os.environ.get("MAC")
    stb_id = args.stbid or cfg.get("STBID") or os.environ.get("STBID")
    stb_type = args.type or cfg.get("STBType") or os.environ.get("STB_TYPE") or "EC6108V9U_pub_cqydx"
    version = args.ver or cfg.get("SoftwareVersion") or os.environ.get("SOFTWARE_VERSION")

    if not (user_id and mac and stb_id and version):
        print("缺少必要参数。请通过 --user/--mac/--stbid/--ver 或 config.yaml 提供：")
        print("  UserID、mac、STBID、SoftwareVersion")
        sys.exit(1)

    # ---- 步骤 1：公网升级入口，302 指向内网升级服务器 ----
    url1 = (f"{PUBLIC_UPGRADE}?TYPE={args.type}"
            f"&STBID={args.stbid}"
            f"&MAC={args.mac}"
            f"&USER={args.user}"
            f"&VER={args.ver}"
            f"&SoftwareVersion={args.ver}"
            f"&SoftwareHWVersion={args.ver}"
            f"&HardwareVersion={args.type}"
            f"&CHECKSUM={args.checksum}")
    print(f"[1/4] 请求公网升级入口: {PUBLIC_UPGRADE}?...")
    try:
        final_url, _, _ = http_get(url1)
    except HTTPError as e:
        print(f"公网入口请求失败: HTTP {e.code} {e.reason}")
        sys.exit(1)
    except URLError as e:
        print(f"公网入口不可达（请确认在重庆电信网络内）: {e}")
        sys.exit(1)

    # 内网升级服务器校验独立的 CHECKSUM（抓包中 21608，与公网 21270 不同）
    final_url_in = re.sub(r"CHECKSUM=[^&]*", f"CHECKSUM={args.checksum_in}", final_url)
    print(f"[2/4] 跟随跳转到: {final_url_in}")
    try:
        _, headers, body = http_get(final_url_in)
    except HTTPError as e:
        print(f"内网升级清单请求失败: HTTP {e.code} {e.reason}")
        sys.exit(1)
    except URLError as e:
        print(f"内网升级服务器不可达: {e}")
        sys.exit(1)

    # Content-Disposition 提示是 config.txt
    disp = headers.get("Content-Disposition", "")
    print(f"      响应类型: {headers.get('Content-Type')}（{disp or '未知'}）")

    sections = parse_config_txt(body.decode("utf-8", errors="replace"))
    if not sections:
        print("响应不是有效的 config.txt 格式：")
        print(body[:500].decode("utf-8", errors="replace"))
        sys.exit(1)

    print(f"[3/4] config.txt 共 {len(sections)} 个固件段:")
    for name, kv in sections.items():
        fname = kv.get("FileName", "?")
        print(f"      - {name}: {fname}")

    target = args.section
    if target not in sections:
        print(f"未找到 [{target}] 段，可用段: {', '.join(sections)}")
        sys.exit(1)
    fname = sections[target].get("FileName")
    if not fname:
        print(f"[{target}] 段缺少 FileName")
        sys.exit(1)

    # ---- 步骤 4：下载固件 ----
    os.makedirs(args.outdir, exist_ok=True)
    last_err = None
    for tmpl in DOWNLOAD_PATHS:
        url = f"http://172.5.129.207:33500{tmpl.format(f=urllib.parse.quote(fname))}"
        print(f"[4/4] 尝试下载: {url}")
        try:
            final, headers, data = http_get(url, timeout=60)
            if len(data) < 1024:
                print(f"      文件过小（{len(data)} 字节），可能不是固件，继续尝试其他路径")
                last_err = "文件过小"
                continue
            out = os.path.join(args.outdir, fname)
            with open(out, "wb") as f:
                f.write(data)
            md5 = headers.get("Content-MD5", "")
            print(f"      下载成功: {out}（{len(data)} 字节）MD5: {md5}")
            print(f"      实际地址: {final}")
            sys.exit(0)
        except HTTPError as e:
            last_err = f"HTTP {e.code}"
            print(f"      HTTP {e.code}，换下一路径")
        except URLError as e:
            last_err = str(e)
            print(f"      失败: {e}，换下一路径")

    print(f"固件下载失败: {last_err}")
    sys.exit(1)


if __name__ == "__main__":
    main()