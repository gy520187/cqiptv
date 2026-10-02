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

var CQ_STYLE = [
    '.cq-page{display:flex;flex-direction:column;gap:16px}',
    '.cq-card{background:rgba(127,127,127,.06);border:1px solid rgba(127,127,127,.22);border-radius:10px;padding:16px}',
    '.cq-hero-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(127,127,127,.18);padding-bottom:10px}',
    '.cq-hero-head h3{margin:0;font-size:15px;font-weight:600}',
    '.cq-hint{color:#999;font-size:12px}',
    '.cq-fields{display:grid;grid-template-columns:repeat(2,1fr);gap:14px 20px;margin:16px 0}',
    '@media(max-width:900px){.cq-fields{grid-template-columns:1fr}}',
    '.cq-field{display:flex;flex-direction:column;gap:6px}',
    '.cq-label{font-size:13px;color:#888;font-weight:500}',
    '.cq-input{width:100%;box-sizing:border-box}',
    '.cq-result{margin:12px 0;padding:10px 12px;border-radius:6px;font-size:13px;display:none}',
    '.cq-result.cq-ok{display:block;background:rgba(46,160,67,.12);border:1px solid rgba(46,160,67,.4);color:#2ea043}',
    '.cq-result.cq-err{display:block;background:rgba(220,50,47,.12);border:1px solid rgba(220,50,47,.4);color:#dc322f}',
    '.cq-actions{display:flex;gap:8px;flex-wrap:wrap}',
    '.cq-btn{border-radius:6px}',
    '.cq-btn-primary{font-weight:600}',
    ''
].join('');

var FIELDS = [
    { name: 'AuthenticationIP', label: '认证服务器地址 (AuthenticationIP)', placeholder: 'http://192.0.2.10:33200/EPG/jsp' },
    { name: 'UserID', label: '用户账号 (UserID)', placeholder: '1234567890@itv' },
    { name: 'mac', label: 'MAC 地址', placeholder: 'AA:BB:CC:DD:EE:FF' },
    { name: 'STBID', label: '机顶盒序列号 (STBID)', placeholder: '00000000000000000000000000000000' },
    { name: 'STBType', label: '机顶盒型号 (STBType)', placeholder: 'ExampleBox_pub_cqydx' },
    { name: 'STBVersion', label: '机顶盒版本 (STBVersion)', placeholder: 'V0000000P0000' },
    { name: 'SoftwareVersion', label: '软件版本 (SoftwareVersion)', placeholder: '1.0.0-EXAMPLE.B001' },
    { name: 'Authenticator', label: 'Authenticator（硬件签名，脱敏显示）', placeholder: '十六进制字符串' },
    { name: 'key', label: '3DES 密钥（脱敏显示，含 * 表示未修改）', placeholder: '' }
];

return view.extend({
    render: function() {
        var el = document.createElement('div');
        var rows = FIELDS.map(function(f) {
            return '<div class="cq-field">' +
                '<label class="cq-label" for="cfg-' + f.name + '">' + esc(f.label) + '</label>' +
                '<input id="cfg-' + f.name + '" class="cbi-input-text cq-input" type="text" ' +
                'placeholder="' + esc(f.placeholder) + '" autocomplete="off">' +
                '</div>';
        }).join('');

        el.innerHTML = [
            '<style>' + CQ_STYLE + '</style>',
            '<div class="cq-page">',
            '  <div class="cq-card">',
            '    <div class="cq-hero-head">',
            '      <h3>IPTV 认证配置</h3>',
            '      <span class="cq-hint">key / Authenticator 脱敏显示，含 * 表示未修改</span>',
            '    </div>',
            '    <div class="cq-fields">' + rows + '</div>',
            '    <div id="cq-result" class="cq-result"></div>',
            '    <div class="cq-actions">',
            '      <button id="cq-btn-test" class="btn cbi-button-action cq-btn">连接测试</button>',
            '      <button id="cq-btn-save" class="btn cbi-button-action cq-btn cq-btn-primary">保存配置</button>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('');

        this.rootEl = el;
        this.loadConfig();
        this.bindActions();
        return el;
    },

    bindActions: function() {
        var self = this;
        this.rootEl.querySelector('#cq-btn-save').addEventListener('click', function() {
            self.save();
        });
        this.rootEl.querySelector('#cq-btn-test').addEventListener('click', function() {
            self.test();
        });
    },

    loadConfig: function() {
        var self = this;
        api('/api/config').then(function(d) {
            FIELDS.forEach(function(f) {
                var input = self.rootEl.querySelector('#cfg-' + f.name);
                if (input) input.value = (d[f.name] != null) ? String(d[f.name]) : '';
            });
        }).catch(function(err) {
            self.showResult('加载配置失败: ' + err, false);
        });
    },

    save: function() {
        var self = this;
        var data = {};
        FIELDS.forEach(function(f) {
            var input = self.rootEl.querySelector('#cfg-' + f.name);
            data[f.name] = input ? input.value : '';
        });
        var btn = this.rootEl.querySelector('#cq-btn-save');
        btn.disabled = true;
        api('/api/config/save', { method: 'POST', body: data })
            .then(function(d) {
                self.showResult(d.msg || (d.ok ? '保存成功' : '保存失败'), !!d.ok);
                if (d.ok) self.loadConfig();
            })
            .catch(function(err) {
                self.showResult('保存失败: ' + err, false);
            })
            .then(function() {
                btn.disabled = false;
            });
    },

    test: function() {
        var self = this;
        var btn = this.rootEl.querySelector('#cq-btn-test');
        btn.disabled = true;
        api('/api/config/test', { method: 'POST', body: {} })
            .then(function(d) {
                self.showResult(d.msg || (d.ok ? '连接成功' : '连接失败'), !!d.ok);
            })
            .catch(function(err) {
                self.showResult('测试失败: ' + err, false);
            })
            .then(function() {
                btn.disabled = false;
            });
    },

    showResult: function(msg, ok) {
        var box = this.rootEl.querySelector('#cq-result');
        box.textContent = msg || '';
        box.className = 'cq-result ' + (ok ? 'cq-ok' : 'cq-err');
    }
});