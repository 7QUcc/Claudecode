// 小克的家 — PWA glue: service worker registration and recovering live
// connections when iOS brings the home-screen app back to the foreground.
(function () {
  'use strict';

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(err => console.warn('sw register failed', err));
    });
  }

  window.xkIsStandalone = () =>
    window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;
  document.documentElement.classList.toggle('standalone', window.xkIsStandalone());

  // iOS freezes background pages and silently kills their EventSource
  // connections. When we come back, reopen the streams and refetch so no
  // message is missed.
  let hiddenAt = 0;
  function resume(reason) {
    const away = hiddenAt ? Date.now() - hiddenAt : 0;
    hiddenAt = 0;
    if (reason === 'visible' && away < 3000) return;
    try {
      if (typeof chSub !== 'undefined' && chSub === 'detail' && typeof activeChat !== 'undefined' && activeChat) {
        if (typeof _chStopRealtimeEvents === 'function') _chStopRealtimeEvents();
        if (typeof _chStartRealtimeEvents === 'function') _chStartRealtimeEvents(activeChat);
        if (typeof _chInvalidateLiveChat === 'function') _chInvalidateLiveChat(activeChat);
        if (typeof renderChatMessages === 'function') renderChatMessages(activeChat);
      }
    } catch (e) { console.warn('chat resume failed', e); }
    try {
      const streamDead = typeof sse !== 'undefined' && (!sse || sse.readyState === 2);
      if (typeof codeSub !== 'undefined' && codeSub === 'detail' && typeof activeSession !== 'undefined' && activeSession
          && (streamDead || away > 20000) && typeof switchSession === 'function') {
        switchSession(activeSession);
      }
    } catch (e) { console.warn('terminal resume failed', e); }
    try { if (typeof loadSessions === 'function') loadSessions(); } catch (e) {}
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') hiddenAt = Date.now();
    else resume('visible');
  });
  window.addEventListener('pageshow', e => { if (e.persisted) resume('pageshow'); });
  window.addEventListener('online', () => resume('online'));

  // Keep the composer glued to the top of the iOS keyboard.
  if (window.visualViewport) {
    const fit = () => {
      document.documentElement.style.setProperty('--vvh', window.visualViewport.height + 'px');
      if (window.visualViewport.offsetTop) window.scrollTo(0, 0);
    };
    window.visualViewport.addEventListener('resize', fit);
    window.visualViewport.addEventListener('scroll', fit);
    fit();
  }

  // ---------- Web Push ----------
  const b64ToBytes = b64 => {
    const pad = '='.repeat((4 - b64.length % 4) % 4);
    const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  };
  const authed = (path, body) => fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (typeof TOKEN !== 'undefined' ? TOKEN : '') },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(async r => { const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.detail || r.status); return j; });

  async function currentSub() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }

  window.xkPush = {
    // 'unsupported' | 'needs-install' | 'denied' | 'off' | 'on'
    async state() {
      if (!('serviceWorker' in navigator)) return 'unsupported';
      const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
      if (!('PushManager' in window)) return ios && !window.xkIsStandalone() ? 'needs-install' : 'unsupported';
      if (Notification.permission === 'denied') return 'denied';
      const sub = await currentSub();
      if (!sub) return 'off';
      const st = await authed('/push/status', { endpoint: sub.endpoint }).catch(() => ({ subscribed: false }));
      return st.subscribed ? 'on' : 'off';
    },
    async prefs() {
      const sub = await currentSub();
      if (!sub) return { done: true, waiting: true };
      return (await authed('/push/status', { endpoint: sub.endpoint })).prefs;
    },
    // Must be called from a tap: iOS only shows the permission prompt then.
    async enable(prefs) {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') throw new Error('没有获得通知权限');
      const { key } = await authed('/push/key');
      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(key) });
      await authed('/push/subscribe', { subscription: sub.toJSON(), prefs });
    },
    async disable() {
      const sub = await currentSub();
      if (!sub) return;
      await authed('/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {});
      await sub.unsubscribe();
    },
    async test() {
      const sub = await currentSub();
      if (!sub) throw new Error('这台设备还没开通知');
      await authed('/push/test', { endpoint: sub.endpoint });
    },
  };

  // Tell the server which session is on screen, so it doesn't buzz the phone
  // about the conversation you're already reading.
  function visibleSession() {
    if (document.visibilityState !== 'visible') return null;
    if (typeof chSub !== 'undefined' && chSub === 'detail' && typeof activeChat !== 'undefined' && activeChat) return activeChat;
    if (typeof codeSub !== 'undefined' && codeSub === 'detail' && typeof activeSession !== 'undefined' && activeSession) return activeSession;
    return null;
  }
  setInterval(() => {
    const s = visibleSession();
    if (s && typeof TOKEN !== 'undefined' && TOKEN) authed('/push/presence', { session: s }).catch(() => {});
  }, 20000);

  // Open the session a notification was about.
  function openSession(name) {
    let tries = 0;
    const attempt = () => {
      const ready = typeof sessions !== 'undefined' && sessions.some(x => x.name === name);
      if (ready && typeof switchView === 'function' && typeof enterChatDetail === 'function') {
        const s = sessions.find(x => x.name === name);
        if (s.kind === 'cc' || s.kind === 'codex' || s.kind === 'opencode') { switchView('chats'); enterChatDetail(name); }
        else if (typeof enterDetail === 'function') { switchView('code'); enterDetail(name); }
        return;
      }
      if (++tries < 40) setTimeout(attempt, 250);
    };
    attempt();
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', e => {
      if (e.data && e.data.type === 'open-session') openSession(e.data.session);
    });
  }
  const startSession = new URLSearchParams(location.search).get('s');
  if (startSession) {
    history.replaceState(null, '', location.pathname);
    window.addEventListener('load', () => openSession(startSession));
  }

  // ---------- Settings → 通知 card ----------
  const PUSH_TEXT = {
    'unsupported': '这个浏览器不支持推送通知。',
    'needs-install': '先把小克的家添加到主屏幕（Safari 分享 → 添加到主屏幕），从主屏幕图标打开后才能开通知。需要 iOS 16.4 或更新。',
    'denied': '通知权限被关掉了。去 iPhone 设置 → 通知 → 小克的家，打开「允许通知」。',
  };
  async function renderPushCard() {
    const card = document.getElementById('stPushCard');
    if (!card) return;
    let st;
    try { st = await window.xkPush.state(); } catch (e) { st = 'off'; }
    if (PUSH_TEXT[st]) { card.innerHTML = `<div class="xk-push-note">${PUSH_TEXT[st]}</div>`; return; }
    const prefs = st === 'on' ? await window.xkPush.prefs().catch(() => ({ done: true, waiting: true })) : { done: true, waiting: true };
    card.innerHTML = `
      <label class="xk-push-row"><span><b>推送通知</b><small>${st === 'on' ? '已开启，这台设备会收到提醒' : '锁屏也能收到小克的提醒'}</small></span>
        <input type="checkbox" class="xk-switch" id="xkPushMain" ${st === 'on' ? 'checked' : ''}></label>
      <label class="xk-push-row"><span>做完一轮时<small>Claude 停下来了，结果可以看了</small></span><input type="checkbox" class="xk-switch" id="xkPushDone" ${prefs.done ? 'checked' : ''} ${st === 'on' ? '' : 'disabled'}></label>
      <label class="xk-push-row"><span>等你回复时<small>权限确认、选择题、提问卡片</small></span><input type="checkbox" class="xk-switch" id="xkPushWaiting" ${prefs.waiting ? 'checked' : ''} ${st === 'on' ? '' : 'disabled'}></label>
      ${st === 'on' ? '<button type="button" class="xk-push-test" id="xkPushTest">发一条测试通知</button>' : ''}
      <div class="xk-push-err" id="xkPushErr"></div>`;
    const err = m => { document.getElementById('xkPushErr').textContent = m || ''; };
    const curPrefs = () => ({ done: document.getElementById('xkPushDone').checked, waiting: document.getElementById('xkPushWaiting').checked });
    document.getElementById('xkPushMain').onchange = async e => {
      err('');
      try { e.target.checked ? await window.xkPush.enable(curPrefs()) : await window.xkPush.disable(); }
      catch (ex) { err(ex.message); }
      renderPushCard();
    };
    ['xkPushDone', 'xkPushWaiting'].forEach(id => document.getElementById(id).onchange = async () => {
      try { await window.xkPush.enable(curPrefs()); } catch (ex) { err(ex.message); }
    });
    const t = document.getElementById('xkPushTest');
    if (t) t.onclick = async () => { err(''); try { await window.xkPush.test(); t.textContent = '已发送，看看锁屏 👀'; } catch (ex) { err(ex.message); } };
  }
  window.xkRenderPushCard = renderPushCard;
  window.addEventListener('load', () => setTimeout(renderPushCard, 300));
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') renderPushCard(); });
})();
