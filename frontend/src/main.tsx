import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import LandingPage from "./landing/LandingPage";
import LoginPage from "./login/LoginPage";
import { getToken, loginUrl } from "./api/session";
import "./styles/tokens.css";
import "./styles/fonts.css";
import "./styles.css";

const APP_BASE = "/app";

// Chooses the landing page for "/", the login page for /login, sends signed-out visitors of /app to login, the existing app under /app, and redirects older app URLs into /app.
function Root() {
  const { pathname, search, hash } = window.location;
  if (pathname === "/") return <LandingPage />;
  if (pathname === "/login") return <LoginPage />;
  if (pathname !== APP_BASE && !pathname.startsWith(`${APP_BASE}/`)) {
    window.location.replace(`${APP_BASE}${pathname}${search}${hash}`);
    return null;
  }
  if (!getToken()) {
    window.location.replace(loginUrl(`${pathname}${search}${hash}`));
    return null;
  }
  return (
    <BrowserRouter basename={APP_BASE}>
      <App />
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
