'use strict';
'require view';
'require ui';

function apiBase() {
    return 'http://' + (window.location.hostname || 'localhost') + ':6061';
}

function api(path, opts) {
    opts = opts || {};
    if (opts.body && typeof opts.body !== 'string') {
        opts.body = JSON.stringify(opts.body);
        opts.headers = opts.headers || {};
        opts.headers['Content-Type'] = 'application/json';
    }
    return fetch(apiBase() + path, opts).then(function(r) { return r.json(); });
}

function esc(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function fmtSize(n) {
    if (!n && n !== 0) return '-';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(2) + ' MB';
}

function fmtTime(ts) {
    if (!ts) return '-';
    var d = new Date(ts * 1000);
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
        ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

var CQ_STYLE = [
    '.cq-page{display:flex;flex-direction:column;gap:16px}',
    '.cq-card{background:rgba(127,127,127,.06);border:1px solid rgba(127,127,127,.22);border-radius:10px;padding:16px}',
    '.cq-card>h3{margin:0 0 12px;font-size:15px;font-weight:600;border-bottom:1px solid rgba(127,127,127,.18);padding-bottom:10px}',
    '.cq-hero-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(127,127,127,.18);padding-bottom:10px}',
    '.cq-hero-head h3{margin:0;border-bottom:0;padding-bottom:0}',
    '.cq-hint{color:#999;font-size:12px}',
    '.cq-grid{display:grid;gap:12px;margin:14px 0}',
    '.cq-grid-4{grid-template-columns:repeat(4,1fr)}',
    '@media(max-width:900px){.cq-grid-4{grid-template-columns:repeat(2,1fr)}}',
    '.cq-stat{background:rgba(127,127,127,.08);border:1px solid rgba(127,127,127,.15);border-radius:8px;padding:14px 10px;text-align:center}',
    '.cq-stat-value{font-size:26px;font-weight:600;color:#1a6fb5;font-variant-numeric:tabular-nums}',
    '.cq-stat-key{font-size:14px;word-break:break-all}',
    '.cq-stat-label{font-size:12px;color:#888;margin-top:4px}',
    '.cq-actions{display:flex;gap:8px;flex-wrap:wrap}',
    '.cq-btn{border-radius:6px}',
    '.cq-btn-primary{font-weight:600}',
    '.cq-logs{max-height:320px;overflow:auto;background:#16181d;color:#d5d9e0;padding:12px;border-radius:6px;font-size:12px;line-height:1.55;white-space:pre-wrap;word-break:break-all}',
    '.cq-empty{color:#999;text-align:center;padding:10px 0}',
    ''
].join('');

return view.extend({
    render: function() {
        var el = document.createElement('div');
        el.innerHTML = [
            '<style>' + CQ_STYLE + '</style>',
            '<div class="cq-page">',
            '  <div class="cq-card">',
            '    <div class="cq-hero-head">',
            '      <h3>IPTV 采集状态</h3>',
            '      <span id="cq-last-refresh" class="cq-hint"></span>',
            '    </div>',
            '    <div class="cq-grid cq-grid-4">',
            '      <div class="cq-stat"><div class="cq-stat-value" id="cq-status-channels">-</div><div class="cq-stat-label">频道数</div></div>',
            '      <div class="cq-stat"><div class="cq-stat-value" id="cq-status-epg">-</div><div class="cq-stat-label">EPG 频道</div></div>',
            '      <div class="cq-stat"><div class="cq-stat-value" id="cq-status-days">-</div><div class="cq-stat-label">EPG 天数</div></div>',
            '      <div class="cq-stat"><div class="cq-stat-value cq-stat-key" id="cq-status-key">-</div><div class="cq-stat-label">key</div></div>',
            '    </div>',
            '    <div class="cq-actions">',
            '      <a id="cq-btn-web" class="btn cbi-button-action cq-btn" target="_blank" rel="noopener">访问 Web 界面</a>',
            '      <button id="cq-btn-collect" class="btn cbi-button-action cq-btn cq-btn-primary">立即采集</button>',
            '      <button id="cq-btn-refresh" class="btn cbi-button-action cq-btn">强制刷新 EPG</button>',
            '    </div>',
            '  </div>',
            '  <div class="cq-card">',
            '    <h3>输出文件</h3>',
            '    <table class="table" width="100%">',
            '      <thead><tr><th>文件</th><th>大小</th><th>更新时间</th><th></th></tr></thead>',
            '      <tbody id="cq-files"><tr><td colspan="4" class="cq-empty">加载中...</td></tr></tbody>',
            '    </table>',
            '  </div>',
            '  <div class="cq-card">',
            '    <h3>运行日志</h3>',
            '    <pre id="cq-logs" class="cq-logs">加载中...</pre>',
            '  </div>',
            '</div>'
        ].join('');

        this.rootEl = el;
        this.bindActions();
        this.loadStatus();
        this.loadLogs();
        this.startAutoRefresh();
        return el;
    },

    bindActions: function() {
        var self = this;
        this.rootEl.querySelector('#cq-btn-web').href = apiBase() + '/';
        this.rootEl.querySelector('#cq-btn-collect').addEventListener('click', function() {
            self.startCollect(false);
        });
        this.rootEl.querySelector('#cq-btn-refresh').addEventListener('click', function() {
            self.startCollect(true);
        });
    },

    startCollect: function(force) {
        var self = this;
        var btns = this.rootEl.querySelectorAll('#cq-btn-collect, #cq-btn-refresh');
        for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
        api('/api/collect', { method: 'POST', body: { force_refresh: force } })
            .then(function(d) {
                ui.addNotification(null, d.msg || (d.ok ? '采集已启动，完成后自动刷新' : '启动失败'));
                if (d.ok) self.pollProgress();
            })
            .catch(function(err) {
                ui.addNotification(null, '请求失败: ' + err);
                for (var i = 0; i < btns.length; i++) btns[i].disabled = false;
            });
    },

    pollProgress: function() {
        var self = this;
        var timer = setInterval(function() {
            api('/api/collect/progress').then(function(p) {
                if (p.done) {
                    clearInterval(timer);
                    var btns = self.rootEl.querySelectorAll('#cq-btn-collect, #cq-btn-refresh');
                    for (var i = 0; i < btns.length; i++) btns[i].disabled = false;
                    self.loadStatus();
                    self.loadLogs();
                }
            }).catch(function() {
                clearInterval(timer);
            });
        }, 2000);
    },

    loadStatus: function() {
        var self = this;
        api('/api/status').then(function(d) {
            self.rootEl.querySelector('#cq-status-channels').textContent = d.channels;
            self.rootEl.querySelector('#cq-status-epg').textContent = d.epg_channels;
            self.rootEl.querySelector('#cq-status-days').textContent = d.epg_days;
            self.rootEl.querySelector('#cq-status-key').textContent = d.key;
            var now = new Date();
            var hint = '上次刷新: ' + fmtTime(Math.floor(now.getTime() / 1000));
            self.rootEl.querySelector('#cq-last-refresh').textContent = hint;
            var tb = self.rootEl.querySelector('#cq-files');
            tb.innerHTML = '';
            if (!d.files || !d.files.length) {
                tb.innerHTML = '<tr><td colspan="4" class="cq-empty">暂无输出文件</td></tr>';
                return;
            }
            (d.files || []).forEach(function(f) {
                var tr = document.createElement('tr');
                tr.innerHTML = '<td>' + esc(f.name) + '</td>' +
                    '<td>' + fmtSize(f.size) + '</td>' +
                    '<td>' + fmtTime(f.mtime) + '</td>' +
                    '<td><a href="' + apiBase() + '/' + esc(f.name) +
                    '" target="_blank" rel="noopener" class="btn cbi-button-action">下载</a></td>';
                tb.appendChild(tr);
            });
        }).catch(function() {
            self.rootEl.querySelector('#cq-last-refresh').textContent = '状态刷新失败';
        });
    },

    loadLogs: function() {
        var self = this;
        api('/api/logs?lines=100').then(function(lines) {
            self.rootEl.querySelector('#cq-logs').textContent = (lines || []).join('\n') || '(暂无日志)';
        }).catch(function() {
            self.rootEl.querySelector('#cq-logs').textContent = '(日志加载失败)';
        });
    },

    startAutoRefresh: function() {
        var self = this;
        var timer = setInterval(function() {
            if (!document.body.contains(self.rootEl)) {
                clearInterval(timer);
                return;
            }
            self.loadStatus();
            self.loadLogs();
        }, 60000);
    },

    handleSave: null,
    handleReset: null
});