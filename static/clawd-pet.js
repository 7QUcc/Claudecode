(function () {
  'use strict';

  const PET_ID = 'xkClawdPet';
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
    pet.title = '小克 · ' + LABELS[nextState];
    pet.setAttribute('aria-label', pet.title);
    image.src = ASSETS[nextState];
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
    observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style', 'data-sub'] });
    window.addEventListener('hashchange', scheduleRefresh);
    window.setInterval(scheduleRefresh, 1200);
    scheduleRefresh();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
