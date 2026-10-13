(() => {
    'use strict';
    const root = document.getElementById('camera-monitor');
    if (!root) return;
    const el = name => document.getElementById('camera-' + name);
    const video = el('preview');
    const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
    let stream = null, cameraId = null, generation = 0, uploadTimer = null, pollTimer = null;
    let lastResult = '', lastWarning = 0, audio = null;

    function message(text, kind = 'secondary') {
        el('status').textContent = text;
        el('status').className = 'alert alert-' + kind + ' mt-3';
    }

    async function api(url, data, keepalive = false) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 12000);
        try {
            const response = await fetch(url, {
                method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: data === undefined ? undefined : JSON.stringify(data),
                cache: 'no-store', signal: controller.signal, keepalive,
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                const error = new Error(result.message || '请求失败，请检查网络或重新登录。');
                error.status = response.status;
                throw error;
            }
            return result;
        } finally { clearTimeout(timer); }
    }

    function stopRemote(id) {
        if (id) api('/api/cameras/' + id + '/stop/', {}, true).catch(() => {});
    }

    function stop(text = '摄像头和分析已停止。', kind = 'secondary') {
        generation++;
        clearTimeout(uploadTimer);
        clearTimeout(pollTimer);
        if (stream) stream.getTracks().forEach(track => track.stop());
        stream = null;
        video.srcObject = null;
        stopRemote(cameraId);
        cameraId = null;
        el('start').disabled = false;
        el('stop').disabled = true;
        ['name', 'facing', 'consent'].forEach(name => { el(name).disabled = false; });
        message(text, kind);
    }

    function beep() {
        if (!audio || audio.state !== 'running') return;
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        oscillator.frequency.value = 880;
        gain.gain.value = 0.12;
        oscillator.connect(gain).connect(audio.destination);
        oscillator.start();
        oscillator.stop(audio.currentTime + 0.5);
    }

    async function capture(token) {
        const frames = [];
        const canvas = document.createElement('canvas');
        for (let i = 0; i < 3; i++) {
            if (token !== generation || !stream) return null;
            if (video.readyState < 2 || !video.videoWidth) throw new Error('暂时读不到摄像头画面，请重新开启。');
            const scale = Math.min(640 / video.videoWidth, 640 / video.videoHeight, 1);
            canvas.width = Math.round(video.videoWidth * scale);
            canvas.height = Math.round(video.videoHeight * scale);
            canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
            frames.push(canvas.toDataURL('image/jpeg', 0.7));
            if (i < 2) await new Promise(resolve => setTimeout(resolve, 700));
        }
        return frames;
    }

    async function upload(token) {
        if (token !== generation || !cameraId) return;
        try {
            const frames = await capture(token);
            if (!frames || token !== generation) return;
            await api('/api/cameras/' + cameraId + '/frames/', { frames });
            if (token !== generation) return;
            message('摄像头已开启，正在分析抽样画面……', 'info');
        } catch (error) {
            if (token !== generation) return;
            if (error.status !== 429) {
                stop(error.message || '上传失败，已停止摄像头，请检查网络后重新开启。', 'danger');
                return;
            }
            message('分析忙碌，15 秒后自动尝试发送新画面。', 'warning');
        }
        if (token === generation) uploadTimer = setTimeout(() => upload(token), 15000);
    }

    async function poll(token) {
        if (token !== generation || !cameraId) return;
        try {
            const result = await api('/api/cameras/' + cameraId + '/status/');
            if (token !== generation) return;
            if (!result.active) { stop('此摄像头会话已结束，请重新开启。'); return; }
            if (result.status === 'error') {
                stop(result.reason + ' 摄像头已停止，处理后可重新开启。', 'danger');
                return;
            }
            if (result.completed_at && result.completed_at !== lastResult) {
                lastResult = result.completed_at;
                el('result').textContent = '最近结果（' + new Date(result.completed_at).toLocaleTimeString() + '）：' + result.reason;
                if (result.category && result.category !== 'none') {
                    el('warning-text').textContent = result.reason;
                    el('warning').classList.remove('d-none');
                    if (Date.now() - lastWarning > 120000) { beep(); lastWarning = Date.now(); }
                }
            }
            if (result.status === 'ok' || result.status === 'alert') {
                message('本轮分析完成，等待下一次抽样。', result.status === 'alert' ? 'warning' : 'success');
            }
        } catch (error) {
            if (token !== generation) return;
            stop('无法确认分析状态，摄像头已停止。请检查网络或重新登录。', 'danger');
            return;
        }
        if (token === generation) pollTimer = setTimeout(() => poll(token), 3000);
    }

    el('start').addEventListener('click', async () => {
        if (!el('consent').checked) { message('请先勾选同意发送抽样画面。', 'warning'); return; }
        if (!el('name').value.trim()) { message('请填写设备名称。', 'warning'); return; }
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
            message('当前浏览器无法使用摄像头，请用自带浏览器打开 HTTPS 网址。', 'danger'); return;
        }
        const token = ++generation;
        lastResult = ''; lastWarning = 0;
        el('result').textContent = '等待第一轮分析结果。';
        el('warning').classList.add('d-none');
        el('start').disabled = true;
        el('stop').disabled = false;
        ['name', 'facing', 'consent'].forEach(name => { el(name).disabled = true; });
        message('请允许浏览器使用摄像头……', 'info');
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) { audio = audio || new AudioContext(); audio.resume().catch(() => {}); }
            const opened = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: el('facing').value }, width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false,
            });
            if (token !== generation) { opened.getTracks().forEach(track => track.stop()); return; }
            stream = opened;
            stream.getVideoTracks().forEach(track => track.addEventListener('ended', () => {
                if (token === generation) stop('摄像头已断开，请检查设备后重新开启。', 'warning');
            }));
            video.srcObject = stream;
            await video.play();
            if (token !== generation) return;
            const session = await api(root.dataset.startUrl, { name: el('name').value.trim(), consent: true });
            if (token !== generation) { stopRemote(session.id); return; }
            cameraId = session.id;
            message('摄像头已开启，正在准备抽样画面……', 'info');
            upload(token);
            poll(token);
        } catch (error) {
            if (token !== generation) return;
            const hints = {
                NotAllowedError: '摄像头权限被拒绝。请在浏览器的网站设置中允许摄像头，再重新开启。',
                NotFoundError: '没有找到摄像头，请连接摄像头或换用手机。',
                NotReadableError: '摄像头可能正被其他程序占用，请关闭占用程序后重试。',
            };
            stop(hints[error.name] || error.message || '开启失败，请重试。', 'danger');
        }
    });
    el('stop').addEventListener('click', () => stop());
    el('dismiss').addEventListener('click', () => el('warning').classList.add('d-none'));
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stop('页面已进入后台，摄像头和分析已停止。回来后请重新开启。');
    });
    window.addEventListener('pagehide', () => stop());
})();
