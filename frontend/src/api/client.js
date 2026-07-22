// `??` not `||` on purpose: an explicitly empty string means "same origin"
// (used in the Docker/nginx and Vercel setups where the frontend and API
// share a domain or a proxy) — `||` would wrongly treat that as unset and
// fall back to the localhost default.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

class ApiError extends Error {
  constructor(message, status, code, action) {
    super(message);
    this.status = status;
    this.code = code;
    this.action = action;
  }
}

function getAccessToken() {
  return localStorage.getItem('clauseguard_access_token');
}

function getRefreshToken() {
  return localStorage.getItem('clauseguard_refresh_token');
}

export function setTokens(accessToken, refreshToken) {
  if (accessToken) localStorage.setItem('clauseguard_access_token', accessToken);
  else localStorage.removeItem('clauseguard_access_token');

  if (refreshToken) localStorage.setItem('clauseguard_refresh_token', refreshToken);
  else localStorage.removeItem('clauseguard_refresh_token');
}

export function clearTokens() {
  setTokens(null, null);
}

// Multiple API calls can 401 at the same moment (e.g. a page that fires
// several requests on mount right as the access token expires). Without
// this dedupe, each one would race to refresh independently, and the
// refresh endpoint rotates the refresh token on every call — so the second
// caller's refresh would silently invalidate the first one's brand new
// token. Sharing one in-flight promise means only one refresh actually happens.
let refreshPromise = null;

async function performRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new ApiError('No refresh token available.', 401, 'NO_REFRESH_TOKEN');

  const response = await fetch(`${API_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    clearTokens();
    throw new ApiError('Session expired. Please log in again.', 401, 'SESSION_EXPIRED');
  }

  const data = await response.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token;
}

async function rawRequest(path, options, accessToken) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch (networkErr) {
    console.error(`Network request to ${API_URL}${path} failed:`, networkErr);
    throw new ApiError(
      "Can't reach ClauseGuard right now. Check your connection and try again in a moment.",
      0,
      'NETWORK_ERROR'
    );
  }
  return response;
}

async function request(path, options = {}) {
  const isAuthEndpoint = path.startsWith('/api/auth/login') || path.startsWith('/api/auth/register')
    || path.startsWith('/api/auth/refresh');

  let response = await rawRequest(path, options, isAuthEndpoint ? null : getAccessToken());

  // On a 401 from a non-auth endpoint, try exactly one silent refresh-and-retry.
  if (response.status === 401 && !isAuthEndpoint && getRefreshToken()) {
    try {
      if (!refreshPromise) refreshPromise = performRefresh().finally(() => { refreshPromise = null; });
      const newAccessToken = await refreshPromise;
      response = await rawRequest(path, options, newAccessToken);
    } catch {
      clearTokens();
      throw new ApiError('Your session expired. Please log in again.', 401, 'SESSION_EXPIRED');
    }
  }

  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch {
    // non-JSON response body
  }

  if (!response.ok) {
    const detail = data?.error?.message || data?.detail || response.statusText || 'Request failed.';
    const code = data?.error?.code || 'HTTP_ERROR';
    const action = data?.error?.action || null;
    throw new ApiError(detail, response.status, code, action);
  }

  return data;
}

export const api = {
  register: (email, password) =>
    request('/api/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),

  login: (email, password) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  logout: (refreshToken) =>
    request('/api/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) }),

  logoutAll: () => request('/api/auth/logout-all', { method: 'POST' }),

  me: () => request('/api/auth/me'),

  verifyEmail: (token) =>
    request('/api/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),

  resendVerification: () => request('/api/auth/resend-verification', { method: 'POST' }),

  requestPasswordReset: (email) =>
    request('/api/auth/request-password-reset', { method: 'POST', body: JSON.stringify({ email }) }),

  resetPassword: (token, newPassword) =>
    request('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, new_password: newPassword }) }),

  uploadDocument: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/api/documents/upload', { method: 'POST', body: formData });
  },

  listDocuments: () => request('/api/documents/'),
  getStatus: (id) => request(`/api/documents/${id}/status`),
  getResults: (id) => request(`/api/documents/${id}/results`),
  deleteDocument: (id) => request(`/api/documents/${id}`, { method: 'DELETE' }),

  createCheckoutSession: (plan) =>
    request('/api/billing/create-checkout-session', { method: 'POST', body: JSON.stringify({ plan }) }),

  getUsage: () => request('/api/billing/usage'),
};

export { ApiError };
