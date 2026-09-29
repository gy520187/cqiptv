'use strict';
'require view';
'require ui';

function apiBase() {
    return 'http://' + (window.location.hostname || 'localhost') + ':6060';
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
            return '<tr><th width="30%">' + esc(f.label) + '</th>' +
                '<td><input id="cfg-' + f.name + '" class="cbi-input-text" type="text" ' +
                'placeholder="' + esc(f.placeholder) + '" style="width:95%"></td></tr>';
        }).join('');

        el.innerHTML = [
            '<div class="cbi-section">',
            '  <h3>IPTV 认证配置</h3>',
            '  <div class="cbi-section-node">',
            '    <table class="table" width="100%">',
            rows,
            '    </table>',
            '  </div>',
            '  <div class="cbi-page-actions">',
            '    <button id="cq-btn-test" class="btn cbi-button-action">连接测试</button>',
            '    <button id="cq-btn-save" class="btn cbi-button-action">保存配置</button>',
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
            ui.addNotification(null, '加载配置失败: ' + err);
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
                ui.addNotification(null, d.msg || (d.ok ? '保存成功' : '保存失败'));
                if (d.ok) self.loadConfig();
            })
            .catch(function(err) {
                ui.addNotification(null, '保存失败: ' + err);
            })
            .then(function() {
                btn.disabled = false;
            });
    },

    test: function() {
        var btn = this.rootEl.querySelector('#cq-btn-test');
        btn.disabled = true;
        api('/api/config/test', { method: 'POST', body: {} })
            .then(function(d) {
                ui.addNotification(null, d.msg || (d.ok ? '连接成功' : '连接失败'));
            })
            .catch(function(err) {
                ui.addNotification(null, '测试失败: ' + err);
            })
            .then(function() {
                btn.disabled = false;
            });
    }
});