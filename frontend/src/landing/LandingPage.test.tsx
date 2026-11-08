import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import LandingPage from "./LandingPage";
import { verifyDisplayFont } from "./fontGuard";

const sources = import.meta.glob("./**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<
  string,
  string
>;

// Stubs the window object so prefersReducedMotion sees the given setting.
function stubReducedMotion(matches: boolean) {
  vi.stubGlobal("window", { matchMedia: () => ({ matches }) });
}

// Stubs document.fonts with faces that end in the given load statuses.
function stubFonts(faces: { family: string; style: string; result: "loaded" | "error" }[]) {
  const list = faces.map((f) => {
    const face = { family: f.family, style: f.style, status: "unloaded", load: vi.fn() };
    face.load.mockImplementation(() => {
      face.status = f.result;
      return f.result === "loaded" ? Promise.resolve(face) : Promise.reject(new Error("404"));
    });
    return face;
  });
  vi.stubGlobal("document", { fonts: { forEach: (cb: (f: unknown) => void) => list.forEach(cb) } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("LandingPage", () => {
  // Checks there is exactly one h1, it carries the tagline and the display class.
  it("renders one display h1 with the tagline", () => {
    const html = renderToStaticMarkup(<LandingPage />);
    const h1s = html.match(/<h1[\s>][\s\S]*?<\/h1>/g) ?? [];
    expect(h1s).toHaveLength(1);
    const h1 = h1s[0] ?? "";
    expect(h1.replace(/<[^>]+>/g, "")).toBe("Sift the noise. Keep what matters.");
    expect(h1).toMatch(/class="[^"]*\bsift-display\b/);
  });

  // Checks every primary call-to-action link points at the login page.
  it("links every primary call to action to /login", () => {
    const html = renderToStaticMarkup(<LandingPage />);
    const ctas = html.match(/<a [^>]*sift-btn-primary[^>]*>/g) ?? [];
    expect(ctas.length).toBeGreaterThanOrEqual(3);
    ctas.forEach((tag) => expect(tag).toContain('href="/login"'));
    expect(html).not.toContain('href="/app"');
  });

  // Checks the specimen starts in its finished state when motion is reduced.
  it("shows the finished specimen when reduced motion is on", () => {
    stubReducedMotion(true);
    const html = renderToStaticMarkup(<LandingPage />);
    expect(html).toContain('data-state="done"');
    expect(html).toContain("Analysis ready: summary, key points, one action item, one open question.");
  });

  // Checks the specimen starts raw when motion is allowed.
  it("starts the specimen raw when motion is allowed", () => {
    stubReducedMotion(false);
    expect(renderToStaticMarkup(<LandingPage />)).toContain('data-state="raw"');
  });

  // Checks rendering makes no network calls and no landing file uses fetch or the API client.
  it("makes no network calls", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    renderToStaticMarkup(<LandingPage />);
    expect(fetchSpy).not.toHaveBeenCalled();
    const files = Object.entries(sources).filter(([path]) => !path.endsWith(".test.tsx"));
    expect(files.length).toBeGreaterThan(5);
    files.forEach(([, code]) => {
      expect(code).not.toMatch(/\bfetch\(|XMLHttpRequest|api\/client/);
    });
  });

  // Checks no raster images are used anywhere on the page.
  it("uses no images", () => {
    expect(renderToStaticMarkup(<LandingPage />)).not.toContain("<img");
  });

  // Checks the botanical drawing is identical on every render and hidden from assistive tech.
  it("draws the same decorative botanicals every time", () => {
    const a = renderToStaticMarkup(<LandingPage />);
    const b = renderToStaticMarkup(<LandingPage />);
    const svg = a.match(/<svg class="sift-botanical[\s\S]*?<\/svg>/)?.[0] ?? "";
    expect(svg).toContain('aria-hidden="true"');
    expect(svg.length).toBeGreaterThan(1000);
    expect(b).toContain(svg);
  });
});

describe("verifyDisplayFont", () => {
  // Checks a failed Redaction 50 load returns false and logs an error.
  it("returns false and logs when no face loads", async () => {
    stubFonts([{ family: '"Redaction 50"', style: "normal", result: "error" }]);
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(verifyDisplayFont()).resolves.toBe(false);
    expect(log).toHaveBeenCalledOnce();
  });

  // Checks a missing Redaction 50 face also counts as a failure.
  it("returns false when no Redaction face exists", async () => {
    stubFonts([{ family: "Inter", style: "normal", result: "loaded" }]);
    vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(verifyDisplayFont()).resolves.toBe(false);
  });

  // Checks a loaded Redaction 50 face returns true without logging.
  it("returns true when a face loads", async () => {
    stubFonts([
      { family: "Redaction 50", style: "normal", result: "loaded" },
      { family: "Redaction 50", style: "italic", result: "error" },
    ]);
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(verifyDisplayFont()).resolves.toBe(true);
    expect(log).not.toHaveBeenCalled();
  });
});
