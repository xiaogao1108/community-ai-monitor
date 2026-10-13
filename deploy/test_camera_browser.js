// 无额外依赖：验证异步授权、停止和告警展示行为。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../t7/Python/community_system/static/js/camera-monitor.js'), 'utf8');

function deferred() {
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    return { promise, resolve };
}

function setup(options = {}) {
    const elements = {};
    const events = {};
    const timers = new Map();
    const calls = [];
    let timerId = 0, stopped = 0, permissions = 0;
    for (const name of ['monitor', 'preview', 'status', 'result', 'warning', 'warning-text', 'start', 'stop', 'name', 'facing', 'consent', 'dismiss']) {
        elements['camera-' + name] = { value: name === 'name' ? '测试设备' : 'environment', checked: false,
            textContent: '', disabled: false, dataset: { startUrl: '/api/cameras/start/' }, handlers: {},
            classList: { hidden: true, add() { this.hidden = true; }, remove() { this.hidden = false; } },
            addEventListener(event, callback) { this.handlers[event] = callback; },
            querySelector() { return { value: 'test-csrf' }; } };
    }
    Object.assign(elements['camera-preview'], { readyState: 4, videoWidth: 640, videoHeight: 480, play: async () => {} });
    const track = { stop() { stopped++; }, addEventListener() {} };
    const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
    const document = {
        hidden: false, getElementById: id => elements[id],
        addEventListener: (event, callback) => { events[event] = callback; },
        createElement: () => ({ getContext: () => ({ drawImage() {} }), toDataURL: () => 'data:image/jpeg;base64,test' }),
    };
    const response = result => ({ ok: true, status: 200, json: async () => result });
    vm.runInNewContext(source, {
        document, window: { isSecureContext: true, addEventListener: (event, callback) => { events[event] = callback; } },
        navigator: { mediaDevices: { getUserMedia: () => { permissions++; return options.media ? options.media.promise : Promise.resolve(stream); } } },
        fetch: async (url, args) => {
            calls.push({ url, args });
            if (url.endsWith('/start/')) return options.start ? options.start.promise : response({ id: 'device-1' });
            if (url.endsWith('/status/')) return response(options.result || { active: true, status: 'ready' });
            return response({});
        },
        AbortController, Date, Promise,
        setTimeout: (fn, delay) => { timers.set(++timerId, { fn, delay }); return timerId; },
        clearTimeout: id => timers.delete(id),
    });
    return { elements, events, document, calls, timers, stream, response,
        get stopped() { return stopped; }, get permissions() { return permissions; },
        click: name => elements['camera-' + name].handlers.click(),
    };
}

const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };

test('没有同意不会请求摄像头或上传', async () => {
    const app = setup();
    await app.click('start');
    assert.equal(app.permissions, 0);
    assert.equal(app.calls.length, 0);
});

test('授权等待期间停止，迟到的摄像头立即关闭', async () => {
    const media = deferred();
    const app = setup({ media });
    app.elements['camera-consent'].checked = true;
    const starting = app.click('start');
    app.click('stop');
    media.resolve(app.stream);
    await starting;
    assert.equal(app.stopped, 1);
    assert.equal(app.calls.length, 0);
});

test('启动响应迟到时也会关闭服务端会话', async () => {
    const start = deferred();
    const app = setup({ start });
    app.elements['camera-consent'].checked = true;
    const starting = app.click('start');
    await flush();
    app.click('stop');
    start.resolve(app.response({ id: 'late-device' }));
    await starting;
    assert.ok(app.calls.some(call => call.url === '/api/cameras/late-device/stop/'));
    assert.ok(!app.calls.some(call => call.url.endsWith('/frames/')));
    assert.equal(app.stopped, 1);
});

test('新一轮分析中仍展示上一轮未读火情，不把文本当 HTML', async () => {
    const app = setup({ result: { active: true, status: 'analyzing', category: 'fire', completed_at: '2026-10-13T10:00:00', reason: '<b>疑似火情</b>' } });
    app.elements['camera-consent'].checked = true;
    await app.click('start');
    await flush();
    assert.equal(app.elements['camera-warning'].classList.hidden, false);
    assert.equal(app.elements['camera-warning-text'].textContent, '<b>疑似火情</b>');
    app.click('stop');
    assert.equal(app.stopped, 1);
});

test('页面进入后台会关闭画面并通知服务器', async () => {
    const app = setup();
    app.elements['camera-consent'].checked = true;
    await app.click('start');
    app.document.hidden = true;
    app.events.visibilitychange();
    assert.equal(app.stopped, 1);
    assert.equal(app.elements['camera-preview'].srcObject, null);
    assert.ok(app.calls.some(call => call.url.endsWith('/stop/')));
    for (const timer of [...app.timers.values()]) if (timer.delay === 700) timer.fn();
    await flush();
    assert.ok(!app.calls.some(call => call.url.endsWith('/frames/')));
});

test('模型出错不会显示正常，停止后需要主动重开', async () => {
    const app = setup({ result: { active: true, status: 'error', reason: '余额不足' } });
    app.elements['camera-consent'].checked = true;
    await app.click('start');
    await flush();
    assert.match(app.elements['camera-status'].textContent, /余额不足/);
    assert.equal(app.stopped, 1);
    assert.equal(app.elements['camera-stop'].disabled, true);
});
