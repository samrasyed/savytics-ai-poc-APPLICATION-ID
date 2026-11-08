import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import "../landing/landing.css";
import "./login.css";
import { ApiError, getMe, login, register } from "../api/client";
import { clearToken, getToken, nextPath, setToken } from "../api/session";
import LogoMark from "../landing/components/LogoMark";

type Mode = "login" | "register";
type FieldError = { field: "email" | "password" | "form"; message: string } | null;

const COPY = {
  login: {
    title: "Welcome back.",
    sub: "Log in to see your past analyses.",
    submit: "Log in",
    busy: "Logging in…",
    switchText: "No account?",
    switchAction: "Create one",
    passwordAutocomplete: "current-password",
  },
  register: {
    title: "Create your account.",
    sub: "Your analyses stay private to you.",
    submit: "Create account",
    busy: "Creating account…",
    switchText: "Already have an account?",
    switchAction: "Log in",
    passwordAutocomplete: "new-password",
  },
} as const;

// Checks the email and password and returns the first problem found.
function validate(email: string, password: string): FieldError {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { field: "email", message: "Enter a valid email address." };
  if (password.length < 8) return { field: "password", message: "Password must be at least 8 characters." };
  return null;
}

// Turns a backend error into a message placed on the right field.
function toFieldError(err: unknown): FieldError {
  if (!(err instanceof ApiError)) return { field: "form", message: "Something went wrong. Please try again." };
  if (err.code === "EMAIL_TAKEN") return { field: "email", message: err.message };
  if (err.code === "VALIDATION_ERROR") {
    const first = (err.details as { field?: string; reason?: string }[] | undefined)?.[0];
    const field = first?.field === "email" || first?.field === "password" ? first.field : "form";
    return { field, message: first?.reason ?? err.message };
  }
  return { field: "form", message: err.message };
}

// Returns to the previous page on this site, or to the landing page when the visitor came from
// elsewhere or from the app (which would only send them straight back here).
function goBack() {
  let fromSite = false;
  try {
    const ref = new URL(document.referrer);
    fromSite = ref.origin === window.location.origin && !ref.pathname.startsWith("/app");
  } catch {
    fromSite = false;
  }
  if (fromSite && window.history.length > 1) window.history.back();
  else window.location.assign("/");
}

// Renders the login page: Sift wordmark on the left, a log-in or sign-up form on the right.
export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<FieldError>(null);
  const [busy, setBusy] = useState(false);
  const copy = COPY[mode];
  const destination = nextPath(window.location.search);

  // Skips the form when a still-valid session is already saved.
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    getMe(token)
      .then(() => window.location.replace(destination))
      .catch(() => clearToken());
  }, [destination]);

  // Validates the form, logs in or registers with the backend, then opens the app.
  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = validate(email.trim(), password);
    setError(problem);
    if (problem) return;
    setBusy(true);
    try {
      const auth = await (mode === "login" ? login : register)(email.trim(), password);
      setToken(auth.token);
      window.location.assign(destination);
    } catch (err) {
      setError(toFieldError(err));
      setBusy(false);
    }
  };

  // Switches between logging in and creating an account, clearing any error.
  const switchMode = () => {
    setMode(mode === "login" ? "register" : "login");
    setError(null);
  };

  return (
    <div className="sift-landing sift-login">
      <div className="sift-login__top">
        <button type="button" className="sift-login__back" onClick={goBack}>
          <ArrowLeft size={16} strokeWidth={1.75} aria-hidden="true" />
          Back
        </button>
        <a href="/" className="sift-brand sift-login__home" aria-label="Sift home">
          <LogoMark size={28} />
          <span className="sift-wordmark sift-display">Sift</span>
        </a>
      </div>
      <main className="sift-login__panel sift-paper">
        <p className="sift-login__brand sift-display" aria-hidden="true">
          Sift
        </p>
        <form className="sift-login__form" onSubmit={onSubmit} noValidate>
          <h1 className="sift-login__title sift-display">{copy.title}</h1>
          <p className="sift-login__sub">{copy.sub}</p>
          <label className="sift-field">
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={error?.field === "email" || undefined}
              required
            />
          </label>
          <label className="sift-field">
            <span>Password</span>
            <input
              type="password"
              autoComplete={copy.passwordAutocomplete}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={error?.field === "password" || undefined}
              required
            />
          </label>
          {error && (
            <p className="sift-login__error" role="alert">
              {error.message}
            </p>
          )}
          <button type="submit" className="sift-btn sift-btn-primary sift-login__submit" disabled={busy}>
            {busy ? copy.busy : copy.submit}
            {!busy && <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />}
          </button>
          <p className="sift-login__alt">
            {copy.switchText}{" "}
            <button type="button" className="sift-login__switch" onClick={switchMode}>
              {copy.switchAction}
            </button>
          </p>
        </form>
      </main>
    </div>
  );
}
