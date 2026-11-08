import type {
  AnalysisListResponse,
  AnalysisRecord,
  ErrorDetail,
  HealthResponse,
} from "./types";
import { getToken, redirectToLogin } from "./session";

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

interface ApiErrorInit {
  status: number;
  code: string;
  message: string;
  retryable: boolean;
  requestId?: string;
  details?: unknown;
  retryAfterSeconds?: number;
}

export class ApiError extends Error {
  status: number;
  code: string;
  retryable: boolean;
  requestId?: string;
  details?: unknown;
  retryAfterSeconds?: number;

  // Builds an error that carries the backend's error code and retry hints.
  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.retryable = init.retryable;
    this.requestId = init.requestId;
    this.details = init.details;
    this.retryAfterSeconds = init.retryAfterSeconds;
  }
}

// Sends a request to the backend and returns the parsed JSON or throws an ApiError.
// A 401 on a signed-in request clears the session and sends the user to the login page.
async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const token = auth ? getToken() : null;
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError({
      status: 0,
      code: "NETWORK_ERROR",
      message: `Cannot reach the server at ${API_URL}. Make sure the backend is running.`,
      retryable: true,
    });
  }

  if (response.status === 204) return undefined as T;

  const body: unknown = await response.json().catch(() => null);
  if (response.status === 401 && auth) redirectToLogin();
  if (!response.ok) {
    const error = (body as { error?: Partial<ErrorDetail> } | null)?.error;
    const retryAfter = Number(response.headers.get("Retry-After"));
    throw new ApiError({
      status: response.status,
      code: error?.code ?? "HTTP_ERROR",
      message: error?.message ?? `The request failed with status ${response.status}.`,
      retryable: error?.retryable ?? response.status >= 500,
      requestId: error?.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
      details: error?.details,
      retryAfterSeconds: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined,
    });
  }
  return body as T;
}

// Sends a document to be analyzed and returns the saved analysis.
export function analyze(title: string, text: string): Promise<AnalysisRecord> {
  return request<AnalysisRecord>("/api/analyses", {
    method: "POST",
    body: JSON.stringify({ title, text }),
  });
}

// Fetches one page of saved analyses, newest first.
export function listAnalyses(limit = 20, offset = 0): Promise<AnalysisListResponse> {
  return request<AnalysisListResponse>(`/api/analyses?limit=${limit}&offset=${offset}`);
}

// Fetches one saved analysis by its ID.
export function getAnalysis(id: string): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(`/api/analyses/${encodeURIComponent(id)}`);
}

// Re-runs the contradiction, risk, dependency and validation checks for one analysis.
export function rerunIntelligence(id: string): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(`/api/analyses/${encodeURIComponent(id)}/intelligence`, {
    method: "POST",
  });
}

// Deletes one saved analysis by its ID.
export function deleteAnalysis(id: string): Promise<void> {
  return request<void>(`/api/analyses/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// Fetches the backend's health and provider status.
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health", {}, false);
}

// Logs in with email and password and returns the session token and user.
export function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
    false,
  );
}

// Creates an account and returns the session token and user.
export function register(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>(
    "/api/auth/register",
    { method: "POST", body: JSON.stringify({ email, password }) },
    false,
  );
}

// Returns the user for a token, without redirecting when the token is no longer valid.
export function getMe(token: string): Promise<User> {
  return request<User>("/api/auth/me", { headers: { Authorization: `Bearer ${token}` } }, false);
}

// Fetches the signed-in user, redirecting to the login page if the session has ended.
export function currentUser(): Promise<User> {
  return request<User>("/api/auth/me");
}

// Ends the session on the server.
export function logout(): Promise<void> {
  return request<void>("/api/auth/logout", { method: "POST" }, true);
}
