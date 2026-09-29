# server.py
import os
import secrets
from flask import Flask, render_template, request, jsonify, Response, send_file, send_from_directory, redirect
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from iptv.web_api import WebAPI

cfg = load_config("config.yaml")
logger = setup_logger(cfg)

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.config["JSON_AS_ASCII"] = False
api = WebAPI(cfg, logger)


@app.context_processor
def inject_static_version():
    """style.css 内容变化后自动更新查询版本号，避免浏览器缓存旧样式"""
    try:
        v = int(os.path.getmtime(os.path.join("web", "static", "style.css")))
    except OSError:
        v = 1
    return {"static_version": v}


@app.after_request
def no_cache_html(response):
    """HTML 不缓存，确保每次访问都拿到最新页面与内联脚本"""
    ct = response.content_type or ""
    if ct.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# 外网访问鉴权: 环境变量 WEB_AUTH=user:password, 留空则不启用
WEB_AUTH = os.getenv("WEB_AUTH", "")
# 播放器直接订阅的数据源与健康检查, 免鉴权
PUBLIC_PREFIXES = ("/playlist.m3u", "/epg.xml", "/data/icon", "/healthz")


@app.after_request
def add_cors_headers(response):
    """允许 LuCI 页面（不同端口）跨域调用 API"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.before_request
def handle_cors_preflight():
    """跨域预检直接返回 200，避免被鉴权拦截"""
    if request.method == "OPTIONS":
        return Response("", 200)


@app.before_request
def check_auth():
    if not WEB_AUTH or ":" not in WEB_AUTH:
        return
    if any(request.path.startswith(p) for p in PUBLIC_PREFIXES):
        return
    user, _, pwd = WEB_AUTH.partition(":")
    auth = request.authorization
    if auth and auth.username == user and secrets.compare_digest(auth.password or "", pwd):
        return
    return Response("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="iptv"'})


@app.before_request
def check_first_run():
    allowed = ("/setup", "/api/config/save", "/api/config/test",
               "/static", "/data/icon", "/healthz")
    if any(request.path.startswith(p) for p in allowed):
        return
    if api.is_first_run() and request.path != "/setup":
        return redirect("/setup")


@app.route("/healthz")
def healthz():
    """容器健康检查端点：始终返回 200，免鉴权、不受首次配置重定向影响"""
    return "ok"


@app.route("/")
def index():
    return render_template("index.html", cfg=cfg)


@app.route("/channels")
def channels_page():
    return render_template("channels.html", cfg=cfg)


@app.route("/epg")
def epg_page():
    return render_template("epg.html", cfg=cfg)


@app.route("/setup")
def setup_page():
    return render_template("setup.html", cfg=cfg)


@app.route("/config")
def config_page():
    return render_template("config.html", cfg=cfg)


@app.route("/crack")
def crack_page():
    return render_template("crack.html", cfg=cfg)


@app.route("/logs")
def logs_page():
    return render_template("logs.html", cfg=cfg)


@app.route("/scheduler")
def scheduler_page():
    return render_template("scheduler.html", cfg=cfg)


@app.route("/api/scheduler/config")
def api_scheduler_config():
    return jsonify(api.get_scheduler_config())


@app.route("/api/scheduler/config", methods=["POST"])
def api_scheduler_save():
    data = request.get_json(silent=True) or {}
    ok, msg = api.save_scheduler_config(data)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/status")
def api_status():
    return jsonify(api.get_status())


@app.route("/api/channels")
def api_channels():
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 50))
    keyword = request.args.get("keyword", "")
    category = request.args.get("category", "")
    return jsonify(api.get_channels(page, size, keyword, category))


@app.route("/api/epg")
def api_epg():
    return jsonify(api.get_epg(request.args.get("channel_id", "")))


@app.route("/api/config")
def api_config():
    return jsonify(api.get_config())


@app.route("/api/config/save", methods=["POST"])
def api_config_save():
    data = request.json or {}
    ok, msg = api.save_config(data)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/config/test", methods=["POST"])
def api_config_test():
    ok, msg = api.test_config()
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/collect", methods=["POST"])
def api_collect():
    data = request.get_json(silent=True) or {}
    ok = api.start_collect(bool(data.get("force_refresh")))
    msg = "强制刷新已启动" if (ok and data.get("force_refresh")) else ("采集已启动" if ok else "采集进行中")
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/collect/progress")
def api_collect_progress():
    import json, threading
    def gen():
        while True:
            p = api.get_collect_progress()
            yield f"data: {json.dumps(p, ensure_ascii=False)}\n\n"
            if p.get("done"):
                break
            threading.Event().wait(1)
    return Response(gen(), mimetype="text/event-stream")


@app.route("/api/crack", methods=["POST"])
def api_crack():
    data = request.json or {}
    ok = api.start_crack(data.get("start"), data.get("end"), data.get("workers"))
    return jsonify({"ok": ok})


@app.route("/api/crack/progress")
def api_crack_progress():
    import json, threading
    def gen():
        while True:
            p = api.get_crack_progress()
            yield f"data: {json.dumps(p, ensure_ascii=False)}\n\n"
            if p.get("done"):
                break
            threading.Event().wait(1)
    return Response(gen(), mimetype="text/event-stream")


@app.route("/api/logs")
def api_logs():
    return jsonify(api.get_logs(int(request.args.get("lines", 200))))


@app.route("/api/download/<path:fn>")
def api_download(fn):
    # send_from_directory 内部用 safe_join 校验路径，阻断 ../ 穿越
    return send_from_directory(constants.OUTPUT_DIR, fn, as_attachment=True)


@app.route("/playlist.m3u")
def playlist():
    return send_file(os.path.join(constants.OUTPUT_DIR, "playlist.m3u"))


@app.route("/epg.xml")
def epg_xml():
    return send_file(os.path.join(constants.OUTPUT_DIR, "epg.xml"))


@app.route("/epg.xml.gz")
def epg_gz():
    return send_file(os.path.join(constants.OUTPUT_DIR, "epg.xml.gz"))


@app.route("/data/icon/<path:fn>")
def icon(fn):
    return send_from_directory(constants.ICON_DIR, fn)


if __name__ == "__main__":
    logger.info(f"Web 启动: http://{constants.WEB_HOST}:{constants.WEB_PORT}")
    app.run(host=constants.WEB_HOST, port=constants.WEB_PORT,
            debug=False, threaded=True)