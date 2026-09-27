# server.py
import os
from flask import Flask, render_template, request, jsonify, Response, send_file, redirect
from iptv.config import load_config
from iptv.logger import setup_logger
from iptv import constants
from iptv.web_api import WebAPI

cfg = load_config("config.yaml")
logger = setup_logger(cfg)

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.config["JSON_AS_ASCII"] = False
api = WebAPI(cfg, logger)


@app.before_request
def check_first_run():
    allowed = ("/setup", "/api/config/save", "/api/config/test",
               "/static", "/data/icon")
    if any(request.path.startswith(p) for p in allowed):
        return
    if api.is_first_run() and request.path != "/setup":
        return redirect("/setup")


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


@app.route("/api/status")
def api_status():
    return jsonify(api.get_status())


@app.route("/api/channels")
def api_channels():
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 50))
    keyword = request.args.get("keyword", "")
    return jsonify(api.get_channels(page, size, keyword))


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
    ok = api.start_collect()
    return jsonify({"ok": ok, "msg": "采集已启动" if ok else "采集进行中"})


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
    path = os.path.join(constants.OUTPUT_DIR, fn)
    if not os.path.exists(path):
        return jsonify({"ok": False, "msg": "文件不存在"}), 404
    return send_file(path, as_attachment=True)


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
    path = os.path.join(constants.ICON_DIR, fn)
    if not os.path.exists(path):
        return "", 404
    return send_file(path)


if __name__ == "__main__":
    logger.info(f"Web 启动: http://{constants.WEB_HOST}:{constants.WEB_PORT}")
    app.run(host=constants.WEB_HOST, port=constants.WEB_PORT,
            debug=False, threaded=True)