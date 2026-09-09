/**
 * Single place that knows how to talk to the backend.
 *
 * Every component calls these helpers rather than fetch() directly, so auth
 * headers, error shape and the base path stay consistent — and swapping token
 * auth for cookies later touches one file.
 */

const TOKEN_KEY = "english-coach-token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(message, { status, code, detail } = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (auth && token) headers.Authorization = `Token ${token}`;

  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", { status: 0 });
  }

  if (response.status === 204) return null;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    // The backend wraps every error as {error: {code, message, detail}}.
    const err = payload?.error ?? {};
    throw new ApiError(err.message || `Request failed (${response.status})`, {
      status: response.status,
      code: err.code,
      detail: err.detail,
    });
  }
  return payload;
}

export const api = {
  login: (username, password) =>
    request("/auth/login/", { method: "POST", body: { username, password }, auth: false }),
  register: (data) => request("/auth/register/", { method: "POST", body: data, auth: false }),
  dashboard: () => request("/dashboard/"),
  todayLesson: (minutes) => request(`/lessons/today/${minutes ? `?minutes=${minutes}` : ""}`),
  profile: () => request("/profile/"),
  updateProfile: (data) => request("/profile/", { method: "PATCH", body: data }),
  aiStatus: () => request("/ai/status/"),
  scenarios: () => request("/practice/speaking-scripts/scenarios/"),
  scripts: () => request("/practice/speaking-scripts/"),
  generateScript: (data) =>
    request("/practice/speaking-scripts/generate/", { method: "POST", body: data }),
  markPracticed: (id) =>
    request(`/practice/speaking-scripts/${id}/practiced/`, { method: "POST" }),
};
