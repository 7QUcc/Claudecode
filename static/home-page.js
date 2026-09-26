// Mobile-first home screen state. The date is local to this browser and does
// not affect the server or any chat data.
(function () {
  'use strict';

  const DATE_KEY = 'prism:start-date';
  const DEFAULT_DATE = '2026-09-01';

  function readDate() {
    try {
      const value = localStorage.getItem(DATE_KEY);
      return /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? value : DEFAULT_DATE;
    } catch (e) {
      return DEFAULT_DATE;
    }
  }

  function daysSince(value) {
    const start = new Date(value + 'T00:00:00');
    const today = new Date();
    const startDay = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
    const todayDay = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
    return Math.max(0, Math.floor((todayDay - startDay) / 86400000));
  }

  function render() {
    const value = readDate();
    const days = document.getElementById('homeDays');
    const input = document.getElementById('stStartDate');
    if (input && input.value !== value) input.value = value;
    if (!days) return;
    const count = daysSince(value);
    days.textContent = count === 0 ? '今天是我们的第一天' : count + ' days together';
    days.classList.toggle('is-empty', !value);
  }

  window.xkSaveStartDate = function (value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return;
    try { localStorage.setItem(DATE_KEY, value); } catch (e) {}
    render();
  };

  window.xkOpenStartDateSettings = function () {
    if (typeof switchView === 'function') switchView('settings');
    setTimeout(() => document.getElementById('stStartDate')?.focus(), 80);
  };

  window.xkRenderHome = render;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render);
  else render();
})();
