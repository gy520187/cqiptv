function toast(msg, ms = 2200) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), ms);
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        toast('已复制');
    } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            toast('已复制');
        } catch (e2) {
            toast('复制失败');
        }
        ta.remove();
    }
}

function fmtSize(n) {
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1024 / 1024).toFixed(2) + ' MB';
}

function fmtTime(ts) {
    const d = new Date(ts * 1000);
    const p = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
           `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/* 采集进度：顶部进度条 */
let collectEs = null;

function showCollect(show) {
    const wrap = document.getElementById('collect-wrap');
    if (!wrap) return;
    if (show) wrap.classList.add('show');
    else wrap.classList.remove('show');
}

function setCollect(msg, pct) {
    const wrap = document.getElementById('collect-wrap');
    if (!wrap) return;
    showCollect(true);
    document.getElementById('collect-msg').textContent = msg || '采集中...';
    document.getElementById('collect-bar').style.width = (pct || 0) + '%';
}

function watchCollect() {
    if (collectEs) collectEs.close();
    collectEs = new EventSource('/api/collect/progress');
    collectEs.onmessage = (e) => {
        const p = JSON.parse(e.data);
        if (p.done) {
            collectEs.close();
            collectEs = null;
            showCollect(false);
            toast(p.msg || '采集完成');
            if (window.location.pathname === '/') loadStatus();
            return;
        }
        setCollect(p.msg, 0);
    };
    showCollect(true);
    setCollect('连接采集进度...', 0);
}

async function startCollect() {
    const force = document.getElementById('collect-force')?.checked || false;
    const r = await fetch('/api/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_refresh: force }),
    });
    const d = await r.json();
    if (d.ok) watchCollect();
    else toast(d.msg || '采集进行中');
}

/* 页面加载时若正在采集则自动连接 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        if (d.collecting) watchCollect();
    } catch (e) { /* 忽略 */ }
});