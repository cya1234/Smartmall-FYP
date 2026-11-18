// js/views/login.js — account page.
//
// Logging in is optional: browsing, the assistant and the score all work signed out.
// What an account changes is *whose* preferences and search history get recorded, so
// two people sharing a demo do not end up with one blended profile.
import { getJSON, postJSON } from '../api.js';
import { esc, t, isZh, toast } from '../ui.js';

export async function render(root, ctx) {
  const state = { mode: 'login', busy: false, error: null, user: ctx.state.user || null };

  async function refresh() {
    try {
      const r = await getJSON('/api/auth/me');
      state.user = r.user || null;
      ctx.state.user = state.user;
    } catch { state.user = null; }
    paint();
  }

  function paint() {
    if (state.user) {
      root.innerHTML = `<section class="container" style="max-width:520px">
        <h1 class="section-title">${esc(isZh() ? '我的帳戶' : 'Your account')}</h1>
        <div class="card">
          <p style="margin:0"><strong>${esc(state.user.name)}</strong></p>
          <p class="muted small" style="margin:4px 0 0">${esc(state.user.email)}</p>
          <p class="muted small" style="margin:14px 0 0">${esc(isZh()
            ? '你的搜尋紀錄與偏好都存在這個帳戶下，其他人登入看不到。'
            : 'Your searches and preferences are stored under this account; other people cannot see them.')}</p>
          <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
            <button class="btn btn-ghost" id="a-out">${esc(isZh() ? '登出' : 'Log out')}</button>
            <button class="btn btn-primary" id="a-shop">${esc(isZh() ? '去逛逛' : 'Browse')}</button>
          </div>
        </div>
      </section>`;
      root.querySelector('#a-out').addEventListener('click', async () => {
        try { await postJSON('/api/auth/logout', {}); } catch { /* best effort */ }
        ctx.state.user = null;
        toast(isZh() ? '已登出' : 'Logged out');
        state.user = null;
        paint();
      });
      root.querySelector('#a-shop').addEventListener('click', () => ctx.navigate('/shop'));
      return;
    }

    const isReg = state.mode === 'register';
    root.innerHTML = `<section class="container" style="max-width:520px">
      <h1 class="section-title">${esc(isZh() ? '登入 / 註冊' : 'Log in / Sign up')}</h1>
      <p class="section-sub">${esc(isZh()
        ? '不登入也可以逛。登入只是讓你的偏好與搜尋紀錄歸到你的帳戶。'
        : 'You can browse without an account. Logging in just keeps your preferences and history under your name.')}</p>

      <div class="card">
        <div class="chips" style="margin-bottom:16px">
          <button class="chip ${!isReg ? 'active' : ''}" id="m-login">${esc(isZh() ? '登入' : 'Log in')}</button>
          <button class="chip ${isReg ? 'active' : ''}" id="m-reg">${esc(isZh() ? '註冊' : 'Sign up')}</button>
        </div>

        ${isReg ? `<label class="muted small">${esc(isZh() ? '名稱' : 'Name')}</label>
        <input id="f-name" class="search-input" style="width:100%;margin:4px 0 14px" autocomplete="nickname" />` : ''}

        <label class="muted small">Email</label>
        <input id="f-email" type="email" class="search-input" style="width:100%;margin:4px 0 14px"
               autocomplete="email" autofocus />

        <label class="muted small">${esc(isZh() ? '密碼' : 'Password')}</label>
        <input id="f-pass" type="password" class="search-input" style="width:100%;margin:4px 0 6px"
               autocomplete="${isReg ? 'new-password' : 'current-password'}" />
        ${isReg ? `<p class="muted small" style="margin:0 0 14px">${esc(isZh() ? '至少 8 個字元' : 'At least 8 characters')}</p>` : '<div style="height:10px"></div>'}

        ${state.error ? `<p class="small" style="color:var(--warn);margin:0 0 12px">${esc(state.error)}</p>` : ''}

        <button class="btn btn-primary" id="f-submit" style="width:100%" ${state.busy ? 'disabled' : ''}>
          ${esc(state.busy ? '…' : isReg ? (isZh() ? '建立帳戶' : 'Create account') : (isZh() ? '登入' : 'Log in'))}
        </button>
      </div>
    </section>`;

    root.querySelector('#m-login').addEventListener('click', () => { state.mode = 'login'; state.error = null; paint(); });
    root.querySelector('#m-reg').addEventListener('click', () => { state.mode = 'register'; state.error = null; paint(); });
    root.querySelector('#f-submit').addEventListener('click', () => submit());

    // Enter submits, because a login form that does not is a login form people hate.
    root.querySelectorAll('input').forEach((el) =>
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); }));
  }

  async function submit() {
    if (state.busy) return;
    const email = (root.querySelector('#f-email')?.value || '').trim();
    const password = root.querySelector('#f-pass')?.value || '';
    const name = (root.querySelector('#f-name')?.value || '').trim();
    if (!email || !password) {
      state.error = isZh() ? '請填 Email 與密碼' : 'Email and password are required';
      paint();
      return;
    }
    state.busy = true;
    state.error = null;
    paint();
    try {
      const path = state.mode === 'register' ? '/api/auth/register' : '/api/auth/login';
      const r = await postJSON(path, { email, password, name });
      if (!r.ok) throw new Error(r.error || 'failed');
      ctx.state.user = r.user;
      try { localStorage.setItem('smartmall-user', JSON.stringify(r.user)); } catch { /* ignore */ }
      toast(isZh() ? `歡迎，${r.user.name}` : `Welcome, ${r.user.name}`);
      ctx.navigate('/');
    } catch (err) {
      // The server's error key now survives (see api.js); map it to something a person
      // can act on, in the wording of the form they were actually using.
      const map = {
        invalid_credentials: isZh() ? 'Email 或密碼不正確' : 'Wrong email or password',
        email_taken: isZh() ? '這個 Email 已被使用，請直接登入' : 'That email is already registered — log in instead',
        password_too_short: isZh() ? '密碼至少 8 個字元' : 'Password must be at least 8 characters',
        invalid_email: isZh() ? 'Email 格式不正確' : 'That email does not look valid',
        too_many_attempts: isZh() ? '嘗試次數過多，請 5 分鐘後再試' : 'Too many attempts — try again in 5 minutes',
        'Request failed (500)': isZh() ? '伺服器錯誤，請看終端機' : 'Server error — check the terminal',
      };
      const fallback = state.mode === 'register'
        ? (isZh() ? '註冊失敗' : 'Sign-up failed')
        : (isZh() ? '登入失敗' : 'Log-in failed');
      state.error = map[String(err.message)] || `${fallback} (${err.message})`;
      state.busy = false;
      paint();
    }
  }

  await refresh();
}
