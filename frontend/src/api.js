// Small client for the Flask API.
// Authentication uses an HttpOnly, SameSite=Strict session cookie, which this
// code never sees. Every state-changing request carries the CSRF token that
// the API returns, in the X-CSRF-Token header.

let csrfToken = null;

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || `Request failed (${status})`);
    this.status = status;
    this.code = body?.error;
    this.body = body;
  }
}

async function refreshCsrf() {
  const response = await fetch("/api/auth/csrf", { credentials: "same-origin" });
  const data = await response.json();
  csrfToken = data.csrf_token;
}

async function request(method, path, body, retry = true) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    if (!csrfToken) await refreshCsrf();
    headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (data?.csrf_token) csrfToken = data.csrf_token;
  if (response.status === 403 && data?.error === "csrf_failed" && retry) {
    await refreshCsrf(); // session expired or token rotated: get a fresh one once
    return request(method, path, body, false);
  }
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

export const api = {
  me: () => request("GET", "/auth/me"),
  login: (email, password) => request("POST", "/auth/login", { email, password }),
  register: (email, password) => request("POST", "/auth/register", { email, password }),
  logout: () => request("POST", "/auth/logout", {}),
  logoutAll: () => request("POST", "/auth/logout-all", {}),
  provers: () => request("GET", "/provers"),
  examples: () => request("GET", "/examples"),
  validate: (source) => request("POST", "/validate", { source }),
  verify: (payload) => request("POST", "/verify", payload),
  runs: (offset = 0, limit = 20) => request("GET", `/runs?offset=${offset}&limit=${limit}`),
  run: (id) => request("GET", `/runs/${encodeURIComponent(id)}`),
  deleteRun: (id) => request("DELETE", `/runs/${encodeURIComponent(id)}`),
  problems: () => request("GET", "/problems"),
  saveProblem: (problem) => request("POST", "/problems", problem),
  updateProblem: (id, problem) => request("PUT", `/problems/${encodeURIComponent(id)}`, problem),
  deleteProblem: (id) => request("DELETE", `/problems/${encodeURIComponent(id)}`),
  adminStats: () => request("GET", "/admin/stats"),
};

export function _resetForTests() {
  csrfToken = null;
}
