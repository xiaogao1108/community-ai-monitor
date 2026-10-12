// 全局实时预警监听脚本（项目级静态目录副本）
// 轮询后端 /api/alerts/latest/ 获取最新异常记录，出现新记录时弹窗并播放警示音

(function () {
  const API_URL = "/api/alerts/latest/";
  const POLL_INTERVAL_MS = 2000; // 2秒轮询
  const RECENT_THRESHOLD_MS = 60000; // 近1分钟内的记录，首次也提示
  const STORAGE_ID_KEY = "lastAlertId";
  const STORAGE_TIME_KEY = "lastAlertTime";
  let initialized = false;
  let lastAlertId = Number(localStorage.getItem(STORAGE_ID_KEY) || 0);
  let lastAlertTime = Number(localStorage.getItem(STORAGE_TIME_KEY) || 0);

  function playAlertTone() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = 880; // Hz，警示音频率
      g.gain.value = 0.05; // 合理音量
      o.connect(g);
      g.connect(ctx.destination);
      o.start();
      setTimeout(() => {
        o.stop();
        ctx.close();
      }, 1500);
    } catch (e) {
      // 忽略音频错误，避免阻塞弹窗
      console.warn("Alert audio play failed:", e);
    }
  }

  function showAlertModal(abnormalType, createdAtIso) {
    const modalEl = document.getElementById("globalAlertModal");
    if (!modalEl) return;
    const textEl = document.getElementById("globalAlertText");
    const timeEl = document.getElementById("globalAlertTime");
    if (textEl) textEl.textContent = abnormalType || "检测到异常事件";
    if (timeEl) timeEl.textContent = createdAtIso ? `时间：${createdAtIso}` : "";

    // 同步触发声音
    playAlertTone();

    // 显示模态框（置顶显示）
    const modal = new bootstrap.Modal(modalEl, { backdrop: "static", keyboard: false });
    modal.show();
  }

  async function pollLatest() {
    try {
      const res = await fetch(API_URL, { method: "GET", credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      if (!data || !data.has_data) {
        initialized = true; // 即使无数据也认为已初始化，避免首次弹窗
        return;
      }
      const id = Number(data.abnormal_id || 0);
      const createdAtMs = (() => {
        try {
          return data.created_at ? new Date(data.created_at).getTime() : 0;
        } catch (_) { return 0; }
      })();
      if (!initialized) {
        // 首次加载：如果记录很新（1分钟内），也提示一次
        initialized = true;
        lastAlertId = id;
        lastAlertTime = createdAtMs || Date.now();
        localStorage.setItem(STORAGE_ID_KEY, String(lastAlertId));
        localStorage.setItem(STORAGE_TIME_KEY, String(lastAlertTime));
        const now = Date.now();
        if (createdAtMs && now - createdAtMs <= RECENT_THRESHOLD_MS) {
          showAlertModal(data.abnormal_type, data.created_at);
        }
        return;
      }
      // 时间戳优先：只要创建时间晚于本地记录，就触发
      if (createdAtMs && createdAtMs > lastAlertTime) {
        lastAlertTime = createdAtMs;
        localStorage.setItem(STORAGE_TIME_KEY, String(lastAlertTime));
        // 同步更新ID（若后端不保证递增也不影响）
        if (id && id !== lastAlertId) {
          lastAlertId = id;
          localStorage.setItem(STORAGE_ID_KEY, String(lastAlertId));
        }
        showAlertModal(data.abnormal_type, data.created_at);
        return;
      }
      // 兼容旧逻辑：若ID递增也触发
      if (id > lastAlertId) {
        lastAlertId = id;
        localStorage.setItem(STORAGE_ID_KEY, String(lastAlertId));
        showAlertModal(data.abnormal_type, data.created_at);
      }
    } catch (e) {
      // 网络错误时忽略，下一轮继续
      console.warn("Alert polling error:", e);
    }
  }

  // 页面加载后启动轮询
  document.addEventListener("DOMContentLoaded", function () {
    // 立即拉取一次以初始化
    pollLatest();
    // 定时轮询
    setInterval(pollLatest, POLL_INTERVAL_MS);
  });
})();