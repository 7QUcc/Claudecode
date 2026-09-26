// 小克的家 — layout layer on top of Prism's app.html / chat-page.js.
//
// Adds the pieces of the 小克的家 design that Prism doesn't have: the
// sidebar navigation with a recent-sessions list and usage bar, the
// 对话 | 终端 segmented switch in session headers, and a "/" command
// button in the chat composer. Everything calls Prism's own functions, so
// the original features keep working underneath.
(function () {
  'use strict';

  const $ = sel => document.querySelector(sel);
  const narrow = () => window.matchMedia('(max-width: 720px)').matches;
  const CHAT_KINDS = ['cc', 'codex', 'opencode'];
  const AGENT_BADGE = { cc: 'CC', codex: 'CX', opencode: 'OC', shell: 'SH' };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const allSessions = () => (typeof sessions !== 'undefined' && Array.isArray(sessions) ? sessions : []);
  const lastActive = s => s.last_message_at || s.log_mtime || s.created || 0;
  // Same rule Prism's session cards use: anything active in the last 10 min counts as running.
  const isRunning = s => Date.now() / 1000 - lastActive(s) < 600;

  function closeSidebarOnPhone() {
    if (narrow() && typeof toggleSidebar === 'function') toggleSidebar(false);
  }

  // ---------- navigation ----------
  function toChatsList() {
    switchView('chats');
    if (typeof chSub !== 'undefined' && chSub === 'detail' && typeof chBackFromDetail === 'function') chBackFromDetail();
  }
  function toCodeList() {
    switchView('code');
    if (typeof codeSub !== 'undefined' && codeSub === 'detail' && typeof exitDetail === 'function') exitDetail();
  }
  window.xkNav = function (where) {
    switch (where) {
      case 'home':
        switchView('home');
        break;
      case 'new':
        if (typeof openNewSessionModal === 'function') openNewSessionModal();
        break;
      case 'chats':
        toChatsList();
        break;
      case 'code':
        toCodeList();
        break;
      case 'search':
        toChatsList();
        setTimeout(() => {
          const input = document.getElementById('clSearchInput');
          if (input) { input.focus(); if (typeof chSearchFocus === 'function') chSearchFocus(); }
        }, 60);
        break;
      case 'archived':
        toChatsList();
        setTimeout(() => {
          const card = $('.ch-archive-card');
          if (!card) return;
          if (!card.classList.contains('open')) card.querySelector('.ch-archive-head')?.click();
          card.scrollIntoView({ block: 'start', behavior: 'smooth' });
        }, 80);
        break;
      case 'settings':
        switchView('settings');
        if (typeof backToSettingsList === 'function') backToSettingsList();
        break;
      case 'usage':
        switchView('settings');
        if (typeof backToSettingsList === 'function') backToSettingsList();
        setTimeout(() => document.getElementById('stUsageCard')?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 60);
        break;
    }
    closeSidebarOnPhone();
  };

  window.xkOpenSession = function (name) {
    const s = allSessions().find(x => x.name === name);
    if (!s) return;
    if (CHAT_KINDS.includes(s.kind)) { switchView('chats'); enterChatDetail(name); }
    else { switchView('code'); enterDetail(name); }
    closeSidebarOnPhone();
  };

  // ---------- sidebar: recent sessions ----------
  function currentSessionName() {
    if (typeof currentView === 'undefined') return null;
    if (currentView === 'chats' && typeof chSub !== 'undefined' && chSub === 'detail') return typeof activeChat !== 'undefined' ? activeChat : null;
    if (currentView === 'code' && typeof codeSub !== 'undefined' && codeSub === 'detail') return typeof activeSession !== 'undefined' ? activeSession : null;
    return null;
  }
  let recentsSig = '';
  function renderRecents() {
    const box = document.getElementById('xkRecents');
    if (!box) return;
    const list = allSessions().slice().sort((a, b) => lastActive(b) - lastActive(a));
    const cur = currentSessionName();
    const sig = cur + '|' + list.map(s => [s.name, s.chat_name, s.display_name, s.kind, isRunning(s)].join(':')).join(',');
    if (sig === recentsSig) return;
    recentsSig = sig;
    box.innerHTML = list.length ? list.map(s => {
      const title = s.chat_name || s.display_name || s.name;
      return `<button type="button" class="xk-recent${s.name === cur ? ' active' : ''}" data-name="${esc(s.name)}" title="${esc(s.cwd_short || s.cwd || '')}">
        <span class="xk-dot${isRunning(s) ? ' running' : ''}"></span>
        <span class="xk-recent-t">${esc(title)}</span>
        <span class="xk-badge">${AGENT_BADGE[s.kind] || 'SH'}</span>
      </button>`;
    }).join('') : '<div class="xk-recent-empty">还没有会话，点上面「新建会话」</div>';
    box.querySelectorAll('.xk-recent').forEach(b => { b.onclick = () => xkOpenSession(b.dataset.name); });
    const online = document.getElementById('xkOnline');
    if (online) online.textContent = list.length ? String(list.length) : '';
  }

  // ---------- sidebar: usage bar ----------
  async function refreshUsage() {
    const el = document.getElementById('xkUsage');
    if (!el || typeof TOKEN === 'undefined' || !TOKEN) return;
    try {
      const r = await fetch(API + '/usage', { headers: { Authorization: 'Bearer ' + TOKEN } });
      if (!r.ok) return;
      const d = await r.json();
      const w = d.claude && d.claude.ok && d.claude.windows && (d.claude.windows.five_hour || Object.values(d.claude.windows)[0]);
      if (!w) { el.hidden = true; return; }
      const pct = Math.max(0, Math.min(100, Math.round(w.utilization)));
      document.getElementById('xkUsageLabel').textContent = 'Claude Code · ' + (w.label || '5 小时');
      document.getElementById('xkUsagePct').textContent = pct + '%';
      const bar = document.getElementById('xkUsageBar');
      bar.style.width = pct + '%';
      bar.classList.toggle('hot', pct >= 85);
      el.hidden = false;
    } catch (e) { /* offline: keep the last value */ }
  }

  // ---------- 对话 | 终端 segmented switch ----------
  const SEG_HTML =
    '<span class="xk-seg-thumb"></span>' +
    '<button type="button" data-m="chat" aria-label="对话"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg><span>对话</span></button>' +
    '<button type="button" data-m="term" aria-label="终端"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 9 3 3-3 3M13 15h4"/></svg><span>终端</span></button>';

  function placeThumb(seg, mode, instant) {
    const btn = seg.querySelector(`button[data-m="${mode}"]`);
    const thumb = seg.querySelector('.xk-seg-thumb');
    if (!btn || !thumb || !btn.offsetWidth) return;
    if (instant) thumb.style.transition = 'none';
    thumb.style.width = btn.offsetWidth + 'px';
    thumb.style.transform = `translateX(${btn.offsetLeft}px)`;
    seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b === btn));
    if (instant) { void thumb.offsetWidth; thumb.style.transition = ''; }
  }
  // Slide the thumb from the other side each time a header shows up, so
  // switching views reads as one control moving.
  function animateSeg(seg, mode) {
    placeThumb(seg, mode === 'chat' ? 'term' : 'chat', true);
    requestAnimationFrame(() => requestAnimationFrame(() => placeThumb(seg, mode)));
  }
  function makeSeg(mode, onOther) {
    const seg = document.createElement('div');
    seg.className = 'xk-seg';
    seg.setAttribute('role', 'tablist');
    seg.innerHTML = SEG_HTML;
    seg.querySelector(`button[data-m="${mode === 'chat' ? 'term' : 'chat'}"]`).onclick = () => {
      placeThumb(seg, mode === 'chat' ? 'term' : 'chat');
      setTimeout(onOther, 170);
    };
    return seg;
  }
  let chatSeg = null, codeSeg = null;
  function installSegs() {
    // Chat and terminal are separate top-level mobile tabs. The old inline
    // segmented switch is intentionally not injected into either detail view.
    return;
  }
  function syncSegs() {
    const chatsView = document.getElementById('chatsView');
    const codeView = document.getElementById('codeView');
    if (chatSeg) {
      const archive = typeof chViewingArchive !== 'undefined' && chViewingArchive;
      const unified = typeof chViewingUnified !== 'undefined' && chViewingUnified;
      chatSeg.hidden = Boolean(archive || unified);
    }
    if (codeSeg) {
      const s = allSessions().find(x => typeof activeSession !== 'undefined' && x.name === activeSession);
      codeSeg.hidden = !(s && CHAT_KINDS.includes(s.kind));
    }
    const chatShown = chatsView?.classList.contains('active') && chatsView.getAttribute('data-sub') === 'detail';
    const codeShown = codeView?.classList.contains('active') && codeView.getAttribute('data-sub') === 'detail';
    if (chatShown && !syncSegs.chatWas && chatSeg && !chatSeg.hidden) animateSeg(chatSeg, 'chat');
    if (codeShown && !syncSegs.codeWas && codeSeg && !codeSeg.hidden) animateSeg(codeSeg, 'term');
    syncSegs.chatWas = chatShown;
    syncSegs.codeWas = codeShown;
  }

  // ---------- "/" commands in the chat composer ----------
  function installSlashButton() {
    const actions = $('#chInputBar .ch-input-actions');
    if (!actions || actions.querySelector('.xk-slash')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ch-input-btn xk-slash';
    btn.title = '常用命令';
    btn.setAttribute('aria-label', '常用命令');
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3.5" y="3.5" width="17" height="17" rx="4"/><path d="m14.5 7-5 10"/></svg>';
    btn.onclick = openSlashSheet;
    const attach = actions.querySelector('.ch-input-btn');
    if (attach) attach.after(btn); else actions.prepend(btn);
  }
  function openSlashSheet() {
    const list = typeof SHORTCUTS !== 'undefined' ? SHORTCUTS : [];
    if (typeof _xkSheetOpen !== 'function') return;
    _xkSheetOpen({
      title: '常用命令',
      render(page) {
        const box = document.createElement('div');
        box.className = 'xk-step-list';
        list.forEach(it => {
          const row = document.createElement('button');
          row.type = 'button';
          row.className = 'xk-step xk-cmd';
          row.innerHTML = `<span class="xk-step-text"><code>${esc(it.cmd)}</code></span><span class="xk-step-meta">${esc(it.desc)}</span>`;
          row.onclick = () => {
            xkCloseSheet();
            const input = document.getElementById('chInput');
            if (!input) return;
            input.value = it.cmd;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.focus();
          };
          box.appendChild(row);
        });
        page.appendChild(box);
      },
    });
  }

  // ---------- phone: swipe from the left edge opens the sidebar ----------
  (function edgeSwipe() {
    let x0 = null, y0 = 0, fromEdge = false;
    window.addEventListener('touchstart', e => {
      const t = e.touches[0]; x0 = t.clientX; y0 = t.clientY; fromEdge = x0 < 22;
    }, { passive: true });
    window.addEventListener('touchend', e => {
      if (x0 === null || !narrow()) return;
      const t = e.changedTouches[0], dx = t.clientX - x0, dy = Math.abs(t.clientY - y0);
      const sheetOpen = document.querySelector('.xk-sheet.open, .modal-bg.open, .ch-bs.open, .action-sheet.open');
      if (!sheetOpen && dy < 50 && fromEdge && dx > 70) toggleSidebar(true);
      x0 = null;
    }, { passive: true });
  })();

  // ---------- boot ----------
  function tick() {
    installSegs();
    installSlashButton();
    renderRecents();
    syncSegs();
  }
  function boot() {
    const standalone = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;
    const tip = document.getElementById('xkInstall');
    if (tip) tip.hidden = standalone || !/iPhone|iPad|iPod/.test(navigator.userAgent);
    // Desktop starts with the full sidebar, like claude.ai.
    if (!narrow() && typeof toggleSidebar === 'function' && document.getElementById('shell')?.getAttribute('data-sidebar') !== 'open') toggleSidebar(true);
    tick();
    setInterval(tick, 700);
    refreshUsage();
    setInterval(refreshUsage, 5 * 60 * 1000);
    window.addEventListener('resize', () => {
      if (chatSeg && !chatSeg.hidden) placeThumb(chatSeg, 'chat', true);
      if (codeSeg && !codeSeg.hidden) placeThumb(codeSeg, 'term', true);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
