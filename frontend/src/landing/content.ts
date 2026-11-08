export const APP_URL = "/app";
export const LOGIN_URL = "/login";

export type LayerKey = "summary" | "keyPoints" | "actions" | "questions";

export const nav = {
  links: [
    { label: "What you get", href: "#layers" },
    { label: "How it works", href: "#how" },
  ],
  login: "Log in",
  cta: "Open Sift",
};

export const hero = {
  eyebrow: "No. 01 · Text in. Clarity out.",
  titleLines: ["Sift the ", "noise. ", "Keep what "],
  titleItalic: "matters.",
  lead: "Paste a transcript, brief or report. Sift returns a clean summary, key points, action items and the questions still left open.",
  primary: "Try Sift",
  secondary: "See how it works",
  micro: "No account needed. Works in demo mode without an API key.",
};

export type RawPart = string | { layer: LayerKey; text: string };

export const specimen = {
  label: "Specimen no. 014",
  title: "Q3 planning call",
  run: "Sift it",
  replay: "Replay",
  chip: "4 layers · 0.3 s",
  announce: "Analysis ready: summary, key points, one action item, one open question.",
  raw: [
    ["Maya: so are we really ", { layer: "summary", text: "moving launch to March 15" }, "? ok."],
    ["Leo: yes, but ", { layer: "keyPoints", text: "pricing is still all over the place" }, "."],
    ["Maya: ", { layer: "actions", text: "Priya, pricing options by Friday" }, "?"],
    ["Priya: sure. hiring's on hold till Q2 anyway."],
    ["Leo: and ", { layer: "questions", text: "who signs off the budget" }, ", honestly?"],
  ] as RawPart[][],
  rows: [
    { layer: "summary", text: "Launch moves to March 15; pricing must be settled next week." },
    { layer: "keyPoints", text: "Pricing is undecided; hiring paused until Q2." },
    { layer: "actions", text: "Draft pricing options, Priya, Friday." },
    { layer: "questions", text: "Who approves the final budget?" },
  ] as { layer: LayerKey; text: string }[],
};

export const layerMeta: Record<LayerKey, { title: string; tone: string }> = {
  summary: { title: "Summary", tone: "butter" },
  keyPoints: { title: "Key points", tone: "rose" },
  actions: { title: "Action items", tone: "mint" },
  questions: { title: "Open questions", tone: "lavender" },
};

export const layers = {
  eyebrow: "No. 02 · What you get",
  titleLead: "One document, ",
  titleItalic: "four",
  titleEnd: " clear layers.",
  sub: "Every analysis comes back in the same shape, so you always know where to look.",
  rows: [
    { n: "01", key: "summary", body: "The whole story in two to four sentences.", chip: "2–4 sentences" },
    { n: "02", key: "keyPoints", body: "The facts, decisions and findings that carry weight.", chip: "Most important first" },
    { n: "03", key: "actions", body: "Who does what and by when, only when the text says so.", chip: "Owner · Due · Priority" },
    { n: "04", key: "questions", body: "What is unresolved, postponed or still missing.", chip: "Written as questions" },
  ] as { n: string; key: LayerKey; body: string; chip: string }[],
};

export const how = {
  eyebrow: "No. 03 · How it works",
  title: "Three quiet steps.",
  steps: [
    { n: "01", title: "Paste", text: "Drop in a title and your text." },
    { n: "02", title: "Sift", text: "Sift reads it, structures it and checks the result." },
    { n: "03", title: "Act", text: "Review each layer and return to it any time from your history." },
  ],
};

export const assurances = [
  { icon: "shield", title: "Validated, not guessed", text: "Every result is checked against a strict schema before it reaches you." },
  { icon: "history", title: "A record of your work", text: "Each analysis is saved so you can reopen it any time." },
  { icon: "flask", title: "Try it without a key", text: "Demo mode returns realistic samples with no API key needed." },
] as const;

export const finalCta = {
  title: "Ready to sift?",
  sub: "Paste your first document and see it sorted in seconds.",
  cta: "Open Sift",
};

export const footer = {
  copyright: "© 2026 Sift",
  signOff: "Made with care",
  links: [
    { label: "What you get", href: "#layers" },
    { label: "How it works", href: "#how" },
    { label: "Open Sift", href: LOGIN_URL },
  ],
};

export const fontWarning = "Redaction 50 not loaded. Showing the fallback font. See the console.";
