/* embed.js — SmartMall AI widget loader.
 *
 * A merchant adds exactly one line:
 *
 *   <script src="https://your-host/embed.js" data-tenant="smartmall-demo" defer></script>
 *
 * It injects:
 *   1. a floating launcher button (bottom-right by default)
 *   2. an iframe panel holding the assistant + visual search
 *   3. optionally, an inline search bar wherever the host page has
 *      <div data-smartmall-search></div>
 *
 * Everything lives inside one prefixed namespace (smw-) and a shadow-free but
 * uniquely-named stylesheet so it cannot collide with the host store's CSS.
 */
(function () {
  'use strict';

  var script = document.currentScript;
  if (!script || script.dataset.smwLoaded === '1') return;
  script.dataset.smwLoaded = '1';

  var ORIGIN = new URL(script.src, window.location.href).origin;
  var TENANT = script.dataset.tenant || 'smartmall-demo';
  var LANG = script.dataset.lang || 'zh';
  var SIDE = script.dataset.position === 'left' ? 'left' : 'right';
  var LABEL = script.dataset.label || (LANG === 'zh' ? 'AI 購物助手' : 'AI shopping assistant');

  var state = { open: false, iframe: null, storeName: 'SmartMall', pendingQuery: null };

  var CSS = [
    '.smw-launcher{position:fixed;bottom:22px;' + SIDE + ':22px;z-index:2147483000;',
    'display:flex;align-items:center;gap:9px;padding:13px 18px;border:0;border-radius:999px;',
    'background:linear-gradient(135deg,#5b4bf0,#7c5cff);color:#fff;font:600 14px/1 -apple-system,',
    'BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC",sans-serif;cursor:pointer;',
    'box-shadow:0 10px 26px rgba(91,75,240,.38);transition:transform .16s ease,box-shadow .16s ease}',
    '.smw-launcher:hover{transform:translateY(-2px);box-shadow:0 14px 32px rgba(91,75,240,.46)}',
    '.smw-launcher:active{transform:translateY(0)}',
    '.smw-launcher .smw-dot{width:8px;height:8px;border-radius:50%;background:#5ff3a8;',
    'box-shadow:0 0 0 3px rgba(95,243,168,.35)}',
    '.smw-panel{position:fixed;bottom:22px;' + SIDE + ':22px;z-index:2147483001;',
    'width:404px;height:min(660px,calc(100vh - 44px));border-radius:20px;overflow:hidden;',
    'background:#fff;box-shadow:0 28px 70px rgba(18,22,34,.34);',
    'opacity:0;transform:translateY(14px) scale(.98);pointer-events:none;',
    'transition:opacity .2s ease,transform .2s cubic-bezier(.2,.8,.3,1)}',
    '.smw-panel.smw-open{opacity:1;transform:none;pointer-events:auto}',
    '.smw-panel iframe{width:100%;height:100%;border:0;display:block}',
    '.smw-search{display:flex;align-items:center;gap:10px;max-width:640px;margin:0 auto;',
    'padding:12px 16px;border:1px solid #e3e5ee;border-radius:14px;background:#fff;',
    'box-shadow:0 2px 12px rgba(18,22,34,.06);font-family:-apple-system,BlinkMacSystemFont,',
    '"Segoe UI",Roboto,"Noto Sans TC",sans-serif}',
    '.smw-search input{flex:1;border:0;outline:0;font-size:15px;color:#1b1f2a;background:transparent}',
    '.smw-search input::placeholder{color:#9aa0b0}',
    '.smw-search button{border:0;border-radius:10px;padding:9px 16px;cursor:pointer;',
    'background:#5b4bf0;color:#fff;font-weight:600;font-size:13px}',
    '.smw-search .smw-ico{font-size:16px}',
    '@media (max-width:520px){.smw-panel{width:100%;height:100%;bottom:0;' + SIDE + ':0;border-radius:0}',
    '.smw-launcher{bottom:16px;' + SIDE + ':16px}}'
  ].join('');

  function injectStyles() {
    if (document.getElementById('smw-styles')) return;
    var style = document.createElement('style');
    style.id = 'smw-styles';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function widgetUrl(query) {
    var p = new URLSearchParams({ tenant: TENANT, lang: LANG });
    if (query) p.set('q', query);
    return ORIGIN + '/widget.html?' + p.toString();
  }

  function ensurePanel() {
    if (state.iframe) return state.iframe;
    var panel = document.createElement('div');
    panel.className = 'smw-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', LABEL);

    var frame = document.createElement('iframe');
    frame.src = widgetUrl(null);
    frame.title = LABEL;
    frame.setAttribute('allow', 'clipboard-write');
    panel.appendChild(frame);
    document.body.appendChild(panel);

    state.iframe = frame;
    state.panel = panel;

    // The widget can ask the host to close it.
    window.addEventListener('message', function (e) {
      if (e.origin !== ORIGIN) return;
      var d = e.data || {};
      if (d.type === 'smartmall:close') close();
      if (d.type === 'smartmall:ready') {
        frame.contentWindow.postMessage(
          { type: 'smartmall:init', tenant: TENANT, lang: LANG, storeName: state.storeName, query: state.pendingQuery },
          ORIGIN,
        );
        state.pendingQuery = null;
      }
    });

    return frame;
  }

  function open(query) {
    ensurePanel();
    state.pendingQuery = query || null;
    state.open = true;
    state.panel.classList.add('smw-open');
    // If the frame already booted, push the query through without a reload.
    if (state.iframe && state.iframe.contentWindow) {
      state.iframe.contentWindow.postMessage(
        { type: 'smartmall:init', tenant: TENANT, lang: LANG, storeName: state.storeName, query: query || null },
        ORIGIN,
      );
    }
  }

  function close() {
    state.open = false;
    if (state.panel) state.panel.classList.remove('smw-open');
  }

  function track(type, label, value, meta) {
    fetch(ORIGIN + '/api/analytics/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: type, label: label, value: value, meta: meta || null, tenant: TENANT }),
      keepalive: true,
    }).catch(function () {});
  }

  function buildLauncher() {
    var btn = document.createElement('button');
    btn.className = 'smw-launcher';
    btn.type = 'button';
    btn.innerHTML = '<span class="smw-dot"></span><span>' + LABEL + '</span>';
    btn.addEventListener('click', function () {
      if (state.open) { close(); return; }
      track('widget_open', 'launcher', null, { source: 'embed' });
      open(null);
    });
    document.body.appendChild(btn);
    return btn;
  }

  function buildInlineSearch() {
    var slots = document.querySelectorAll('[data-smartmall-search]');
    slots.forEach(function (slot) {
      if (slot.dataset.smwBound === '1') return;
      slot.dataset.smwBound = '1';
      var wrap = document.createElement('form');
      wrap.className = 'smw-search';
      wrap.innerHTML =
        '<span class="smw-ico">🔍</span>' +
        '<input type="search" placeholder="' +
        (LANG === 'zh' ? '描述你的需求，例如「海島婚禮穿什麼」' : 'Describe what you need…') +
        '" />' +
        '<button type="submit">' + (LANG === 'zh' ? '詢問 AI' : 'Ask AI') + '</button>';
      wrap.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = wrap.querySelector('input');
        var q = (input.value || '').trim();
        track('widget_open', 'search-bar', null, { source: 'embed', query: q });
        open(q || null);
      });
      slot.appendChild(wrap);
    });
  }

  function start() {
    injectStyles();
    fetch(ORIGIN + '/api/widget/config?tenant=' + encodeURIComponent(TENANT))
      .then(function (r) { return r.json(); })
      .then(function (cfg) { if (cfg && cfg.storeName) state.storeName = cfg.storeName; })
      .catch(function () {})
      .then(function () {
        buildLauncher();
        buildInlineSearch();
        document.addEventListener('keydown', function (e) {
          if (e.key === 'Escape' && state.open) close();
        });
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
