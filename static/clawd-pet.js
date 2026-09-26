(function () {
  'use strict';

  const PET_ID = 'xkClawdPet';
  const POSITION_KEY = 'xk:clawd-pet-position:v1';
  const ASSET_ROOT = 'static/assets/clawd/';
  const ASSETS = {
    idle: ASSET_ROOT + 'clawd-idle.gif',
    thinking: ASSET_ROOT + 'clawd-thinking.gif',
    working: ASSET_ROOT + 'clawd-typing.gif',
    happy: ASSET_ROOT + 'clawd-happy.gif',
    error: ASSET_ROOT + 'clawd-error.gif',
    attention: ASSET_ROOT + 'clawd-notification.gif',
  };
  const LABELS = {
    idle: '空闲中',
    thinking: '思考中',
    working: '工作中',
    happy: '已完成',
    error: '发生错误',
    attention: '需要关注',
  };

  let pet = null;
  let image = null;
  let observer = null;
  let refreshTimer = null;
  let happyUntil = 0;
  let lastBusy = false;
  let lastAssistantCount = 0;
  let lastChatKey = '';
  let lastState = '';
  let drag = null;

  function isVisible(element) {
    if (!element) return false;
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }

  function hasVisible(selector, root) {
    return Array.from((root || document).querySelectorAll(selector)).some(isVisible);
  }

  function currentChatRoot() {
    const view = document.getElementById('chatsView');
    if (!view || !view.classList.contains('active') || view.dataset.sub !== 'detail') return null;
    return document.getElementById('chMsgs');
  }

  function chatKey() {
    const title = document.getElementById('chDetailTitle');
    return title ? title.textContent : '';
  }

  function setState(nextState) {
    if (!pet || !image || !ASSETS[nextState] || lastState === nextState) return;
    lastState = nextState;
    pet.dataset.state = nextState;
    pet.title = '小克 · ' + LABELS[nextState] + ' · 可拖动调整位置';
    pet.setAttribute('aria-label', pet.title);
    image.src = ASSETS[nextState];
  }

  function clampPosition(left, top) {
    const rect = pet.getBoundingClientRect();
    const width = rect.width || pet.offsetWidth;
    const height = rect.height || pet.offsetHeight;
    return {
      left: Math.max(6, Math.min(window.innerWidth - width - 6, left)),
      top: Math.max(6, Math.min(window.innerHeight - height - 6, top)),
    };
  }

  function setPosition(left, top) {
    const position = clampPosition(left, top);
    pet.style.right = 'auto';
    pet.style.bottom = 'auto';
    pet.style.left = position.left + 'px';
    pet.style.top = position.top + 'px';
  }

  function savePosition() {
    try {
      const rect = pet.getBoundingClientRect();
      localStorage.setItem(POSITION_KEY, JSON.stringify({ left: rect.left, top: rect.top }));
    } catch (e) { /* localStorage may be unavailable */ }
  }

  function restorePosition() {
    try {
      const saved = JSON.parse(localStorage.getItem(POSITION_KEY) || 'null');
      if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) setPosition(saved.left, saved.top);
    } catch (e) { /* ignore malformed or unavailable local storage */ }
  }

  function startDrag(event) {
    if (!pet || (event.pointerType === 'mouse' && event.button !== 0)) return;
    pet.classList.add('is-dragging');
    const rect = pet.getBoundingClientRect();
    drag = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      startX: event.clientX,
      startY: event.clientY,
    };
    if (pet.setPointerCapture) pet.setPointerCapture(event.pointerId);
    event.preventDefault();
  }

  function moveDrag(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    setPosition(event.clientX - drag.offsetX, event.clientY - drag.offsetY);
    event.preventDefault();
  }

  function finishDrag(event) {
    if (!drag || (event && event.pointerId !== drag.pointerId)) return;
    if (pet.releasePointerCapture && pet.hasPointerCapture && pet.hasPointerCapture(drag.pointerId)) {
      pet.releasePointerCapture(drag.pointerId);
    }
    savePosition();
    drag = null;
    pet.classList.remove('is-dragging');
    scheduleRefresh();
  }

  function readState() {
    const root = currentChatRoot();
    if (!root) {
      lastBusy = false;
      lastAssistantCount = 0;
      lastChatKey = '';
      return 'idle';
    }

    const key = chatKey();
    if (key !== lastChatKey) {
      lastChatKey = key;
      lastBusy = false;
      lastAssistantCount = root.querySelectorAll('.ch-bubble.assistant').length;
      happyUntil = 0;
    }

    const assistantCount = root.querySelectorAll('.ch-bubble.assistant').length;
    const error = hasVisible('.xk-step.err, .xk-kv.err, .ch-bubble.user.pending.failed', root);
    const thinking = hasVisible('.ch-reply-waiting, .ch-tool-group.inflight.thinking-inflight', root);
    const working = hasVisible('.ch-tool-group.inflight:not(.thinking-inflight), .xk-act.live, .ch-tool-row.pending', root);
    const busy = thinking || working;

    if (lastBusy && !busy && assistantCount > lastAssistantCount) {
      happyUntil = Date.now() + 2600;
    }
    lastBusy = busy;
    lastAssistantCount = assistantCount;

    if (error) return 'error';
    if (thinking) return 'thinking';
    if (working) return 'working';
    if (happyUntil > Date.now()) return 'happy';
    return 'idle';
  }

  function refresh() {
    refreshTimer = null;
    setState(readState());
    if (happyUntil > Date.now()) {
      refreshTimer = window.setTimeout(refresh, happyUntil - Date.now() + 20);
    }
  }

  function scheduleRefresh() {
    if (refreshTimer) return;
    refreshTimer = window.setTimeout(refresh, 40);
  }

  function mount() {
    pet = document.getElementById(PET_ID);
    if (!pet) return;
    image = pet.querySelector('img');
    if (!image) return;
    pet.addEventListener('pointerdown', startDrag);
    pet.addEventListener('pointermove', moveDrag);
    pet.addEventListener('pointerup', finishDrag);
    pet.addEventListener('pointercancel', finishDrag);
    window.addEventListener('resize', () => {
      if (!pet.style.left || !pet.style.top) return;
      const left = Number.parseFloat(pet.style.left);
      const top = Number.parseFloat(pet.style.top);
      if (!Number.isFinite(left) || !Number.isFinite(top)) return;
      setPosition(left, top);
      savePosition();
    });
    restorePosition();
    observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style', 'data-sub'] });
    window.addEventListener('hashchange', scheduleRefresh);
    window.setInterval(scheduleRefresh, 1200);
    scheduleRefresh();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
