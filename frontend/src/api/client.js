// CYBERPULSE AI — API client.
// Thin fetch wrapper: base /api/v1 (proxied by Vite to :8000), auto Bearer token,
// 401 → /login, JSON handling, readable errors.
const BASE = '/api/v1';
const TOKEN_KEY = 'cp_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = 'GET', body, headers = {}, raw = false } = {}) {
  const opts = { method, headers: { ...headers } };
  const token = getToken();
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body !== undefined) {
    if (body instanceof FormData) opts.body = body;
    else {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
  }
  let res;
  try {
    res = await fetch(BASE + path, opts);
  } catch (e) {
    throw new Error('Network error — is the backend running on :8000?');
  }
  if (res.status === 401) {
    setToken('');
    if (!window.location.pathname.startsWith('/login')) window.location.href = '/login';
    throw new Error('Session expired — please sign in again.');
  }
  if (raw) return res;
  let data = null;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) data = await res.json();
  else data = await res.text();
  if (!res.ok) {
    let msg = res.statusText;
    if (data && typeof data === 'object') {
      if (data.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      else if (data.message) msg = data.message;
    } else if (typeof data === 'string' && data) msg = data.slice(0, 200);
    throw new Error(msg);
  }
  return data;
}

export const api = {
  get: (p, o) => request(p, o),
  post: (p, body, o) => request(p, { ...o, method: 'POST', body }),
  put: (p, body, o) => request(p, { ...o, method: 'PUT', body }),
  del: (p, o) => request(p, { ...o, method: 'DELETE' }),
  // fetch a binary (e.g. PDF report) with auth, return a Blob
  async blob(p) {
    const res = await request(p, { raw: true });
    if (!res.ok) throw new Error('Failed to fetch resource');
    return res.blob();
  },
};