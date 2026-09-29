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

return view.extend({
    render: function() {
        var el = document.createElement('div');
        el.innerHTML = [
            '<div class="cbi-section">',
            '  <h3>IPTV 采集状态</h3>',
            '  <div class="cbi-section-node">',
            '    <table class="table" width="100%">',
            '      <tr><th width="30%">频道数</th><td id="cq-status-channels">-</td></tr>',
            '      <tr><th>EPG 频道</th><td id="cq-status-epg">-</td></tr>',
            '      <tr><th>EPG 天数</th><td id="cq-status-days">-</td></tr>',
            '      <tr><th>key</th><td id="cq-status-key">-</td></tr>',
            '    </table>',
            '  </div>',
            '  <div class="cbi-page-actions">',
            '    <button id="cq-btn-collect" class="btn cbi-button-action">立即采集</button>',
            '    <button id="cq-btn-refresh" class="btn cbi-button-action">强制刷新 EPG</button>',
            '  </div>',
            '  <div class="cbi-section-node">',
            '    <h4>输出文件</h4>',
            '    <table class="table" width="100%">',
            '      <thead><tr><th>文件</th><th>大小</th><th>更新时间</th><th></th></tr></thead>',
            '      <tbody id="cq-files"><tr><td colspan="4">-</td></tr></tbody>',
            '    </table>',
            '  </div>',
            '  <div class="cbi-section-node">',
            '    <h4>运行日志</h4>',
            '    <pre id="cq-logs" style="max-height:320px;overflow:auto;background:#1a1a1a;color:#d8d8d8;padding:8px;white-space:pre-wrap;word-break:break-all"></pre>',
            '  </div>',
            '</div>'
        ].join('');

        this.rootEl = el;
        this.bindActions();
        this.loadStatus();
        this.loadLogs();
        return el;
    },

    bindActions: function() {
        var self = this;
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
                ui.addNotification(null, d.msg || (d.ok ? '采集已启动' : '启动失败'));
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
            var tb = self.rootEl.querySelector('#cq-files');
            tb.innerHTML = '';
            if (!d.files || !d.files.length) {
                tb.innerHTML = '<tr><td colspan="4">暂无输出文件</td></tr>';
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
        });
    },

    loadLogs: function() {
        var self = this;
        api('/api/logs?lines=100').then(function(lines) {
            self.rootEl.querySelector('#cq-logs').textContent = (lines || []).join('\n');
        });
    },

    handleSave: null,
    handleReset: null
});