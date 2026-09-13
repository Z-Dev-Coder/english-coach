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
    // A 401 means the stored token is gone, expired or revoked. Clear it once,
    // centrally, so no caller has to remember to -- and tell the app to show
    // the login screen instead of leaving a shell that fails every request.
    if (response.status === 401 && auth) {
      setToken(null);
      window.dispatchEvent(new Event("english-coach:signed-out"));
    }

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
  logout: () => request("/auth/logout/", { method: "POST" }),
  me: () => request("/auth/me/"),
  dashboard: () => request("/dashboard/"),
  todayPlan: (minutes) => request(`/plan/today/${minutes ? `?minutes=${minutes}` : ""}`),
  profile: () => request("/profile/"),
  updateProfile: (data) => request("/profile/", { method: "PATCH", body: data }),
  aiStatus: () => request("/ai/status/"),
  scenarios: () => request("/practice/speaking-scripts/scenarios/"),

  // --- Review and vocabulary ---
  reviewQueue: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/review/queue/${query ? `?${query}` : ""}`);
  },
  reviewAnswer: (body) => request("/review/answer/", { method: "POST", body }),
  reviewStats: () => request("/review/stats/"),
  vocabulary: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/vocabulary/${query ? `?${query}` : ""}`);
  },
  speakingSupport: ({ prompt = "", expressions = [], withAnswer = false } = {}) => {
    const query = new URLSearchParams();
    if (withAnswer) query.set("with_answer", "1");
    if (prompt) query.set("prompt", prompt);
    // Repeated key, not a joined string: an expression can contain a comma.
    expressions.forEach((value) => value && query.append("expression", value));
    return request(`/skills/speaking-support/?${query.toString()}`);
  },
  shadowingGuide: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/skills/shadowing/guide/${query ? `?${query}` : ""}`);
  },
  addVocabulary: (body) => request("/vocabulary/add/", { method: "POST", body }),
  defineWord: (word) => request(`/vocabulary/define/?word=${encodeURIComponent(word)}`),
  addExtractedVocabulary: (body) =>
    request("/vocabulary/add-extracted/", { method: "POST", body }),

  // --- Skill activities ---
  passages: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/skills/passages/${query ? `?${query}` : ""}`);
  },
  addPassage: (body) => request("/skills/passages/add/", { method: "POST", body }),
  submitDictation: (body) => request("/skills/dictation/", { method: "POST", body }),
  submitShadowing: (body) => request("/skills/shadowing/", { method: "POST", body }),
  submitWriting: (body) => request("/skills/writing/", { method: "POST", body }),
  submitReading: (body) => request("/skills/reading/", { method: "POST", body }),
  drill: () => request("/skills/drill/"),
  submitDrill: (body) => request("/skills/drill/", { method: "POST", body }),
  attempts: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/skills/attempts/${query ? `?${query}` : ""}`);
  },
  skillSummary: () => request("/skills/summary/"),

  // --- Lessons ---
  todayLesson: () => request("/lessons/today/"),
  lessons: () => request("/lessons/"),
  lesson: (id) => request(`/lessons/${id}/`),
  regenerateLesson: (body = {}) =>
    request("/lessons/regenerate/", { method: "POST", body }),
  completeActivity: (lessonId, activityId) =>
    request(`/lessons/${lessonId}/activities/${activityId}/complete/`, { method: "POST" }),
  learnerContext: () => request("/learner-context/"),

  // --- Conversation ---
  conversationScenarios: () => request("/conversations/scenarios/"),
  startConversation: (body) => request("/conversations/start/", { method: "POST", body }),
  sendConversationMessage: (id, body) =>
    request(`/conversations/${id}/say/`, { method: "POST", body }),
  endConversation: (id) => request(`/conversations/${id}/end/`, { method: "POST" }),
  conversations: () => request("/conversations/"),

  // --- Real-world content ---
  todayArticles: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/articles/today/${query ? `?${query}` : ""}`);
  },
  articles: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/articles/${query ? `?${query}` : ""}`);
  },
  prepareArticle: (id, body = {}) =>
    request(`/articles/${id}/prepare/`, { method: "POST", body }),
  ingestContent: (body = {}) => request("/content/ingest/", { method: "POST", body }),
  studyDialogue: (body) => request("/content/dialogue/", { method: "POST", body }),

  // --- Mistake bank ---
  mistakes: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    return request(`/mistakes/${query ? `?${query}` : ""}`);
  },
  mistakeSummary: () => request("/mistakes/summary/"),
  mistakePractice: () => request("/mistakes/practice/"),
  mistakeAvoided: (id) => request(`/mistakes/${id}/avoided/`, { method: "POST" }),
  scripts: () => request("/practice/speaking-scripts/"),
  generateScript: (data) =>
    request("/practice/speaking-scripts/generate/", { method: "POST", body: data }),
  markPracticed: (id) =>
    request(`/practice/speaking-scripts/${id}/practiced/`, { method: "POST" }),
};
