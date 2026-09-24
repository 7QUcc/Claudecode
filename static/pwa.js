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
})();
