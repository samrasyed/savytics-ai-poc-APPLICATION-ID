const TOKEN_KEY = "sift.token";
export const LOGIN_PATH = "/login";

// Reads the saved session token, or null when there is none or storage is blocked.
export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

// Saves the session token, ignoring storage that is blocked.
export function setToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage blocked: the session lasts only for this page */
  }
}

// Removes the saved session token.
export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage blocked: nothing to clear */
  }
}

// Builds the login URL that returns the user to the given path afterwards.
export function loginUrl(next?: string): string {
  return next ? `${LOGIN_PATH}?next=${encodeURIComponent(next)}` : LOGIN_PATH;
}

// Returns a safe in-app path from the ?next= parameter, defaulting to /app.
export function nextPath(search: string): string {
  const next = new URLSearchParams(search).get("next") ?? "";
  return next.startsWith("/app") && !next.startsWith("//") ? next : "/app";
}

// Clears the session and sends the user to the login page, remembering where they were.
export function redirectToLogin(): void {
  clearToken();
  const { pathname, search, hash } = window.location;
  window.location.assign(loginUrl(`${pathname}${search}${hash}`));
}
