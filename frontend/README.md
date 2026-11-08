# Sift frontend

React 18 + TypeScript + Vite. See the [root README](../README.md) for the full architecture and setup.

| Path | Page |
| --- | --- |
| `/` | Landing page |
| `/login` | Log in / create account |
| `/app` | The analyzer (requires a session; redirects to `/login` otherwise) |

```bash
cp .env.example .env    # optional: VITE_API_URL defaults to http://localhost:8000
npm install
npm run dev             # http://localhost:5173
npm test                # Vitest suite
npm run build           # type-check + production build
```

Headings use the Redaction 50 font (SIL Open Font License, see `public/fonts/OFL.txt`).

SPA fallback: on static hosting, rewrite every unknown path to `/index.html` so `/app/...` and `/login` deep links load.
