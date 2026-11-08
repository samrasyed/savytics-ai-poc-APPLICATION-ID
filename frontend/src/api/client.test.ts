import { afterEach, describe, expect, it, vi } from "vitest";
import { analyze, ApiError, deleteAnalysis, listAnalyses, rerunIntelligence } from "./client";

// Builds a fake fetch Response with a JSON body, status and headers.
function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

// Replaces the global fetch with a mock that returns the given response.
function mockFetch(response: Response | Error) {
  const fn = vi.fn((_url: string, _init?: RequestInit) =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  // Checks analyze posts JSON to the right URL and returns the record.
  it("posts the document and returns the record", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "abc" }, 201));
    const record = await analyze("Title", "Text");
    expect(record).toEqual({ id: "abc" });
    const [url, init = {}] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/analyses");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ title: "Title", text: "Text" });
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  // Checks list requests pass limit and offset in the query string.
  it("passes paging parameters", async () => {
    const fetchMock = mockFetch(jsonResponse({ items: [], total: 0, limit: 5, offset: 10 }));
    await listAnalyses(5, 10);
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/analyses?limit=5&offset=10");
  });

  // Checks the backend error envelope becomes an ApiError with retry details.
  it("parses the error envelope", async () => {
    mockFetch(
      jsonResponse(
        {
          error: {
            code: "RATE_LIMITED",
            message: "The AI service is busy.",
            retryable: true,
            request_id: "req-1",
            details: null,
          },
        },
        429,
        { "Retry-After": "2" },
      ),
    );
    const error = await analyze("t", "x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      code: "RATE_LIMITED",
      message: "The AI service is busy.",
      retryable: true,
      requestId: "req-1",
      retryAfterSeconds: 2,
    });
  });

  // Checks a failed connection becomes a retryable NETWORK_ERROR.
  it("reports network failures", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    const error = await listAnalyses().catch((e: unknown) => e);
    expect(error).toMatchObject({ code: "NETWORK_ERROR", status: 0, retryable: true });
  });

  // Checks re-running checks posts to the intelligence endpoint.
  it("re-runs intelligence checks", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "abc" }));
    await rerunIntelligence("abc");
    const [url, init = {}] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/analyses/abc/intelligence");
    expect(init.method).toBe("POST");
  });

  // Checks a 204 delete resolves without trying to parse a body.
  it("handles empty delete responses", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(deleteAnalysis("abc")).resolves.toBeUndefined();
  });

  // Checks the saved session token is sent as a bearer header.
  it("sends the session token", async () => {
    vi.stubGlobal("window", { localStorage: { getItem: () => "tok-123" } });
    const fetchMock = mockFetch(jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }));
    await listAnalyses();
    const [, init = {}] = fetchMock.mock.calls[0];
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-123");
  });

  // Checks a 401 clears the session and sends the user to the login page.
  it("redirects to login on 401", async () => {
    const assign = vi.fn();
    const removeItem = vi.fn();
    vi.stubGlobal("window", {
      localStorage: { getItem: () => "old", removeItem },
      location: { pathname: "/app/analyses/1", search: "", hash: "", assign },
    });
    mockFetch(jsonResponse({ error: { code: "AUTH_REQUIRED", message: "Please log in." } }, 401));
    await expect(listAnalyses()).rejects.toBeInstanceOf(ApiError);
    expect(removeItem).toHaveBeenCalled();
    expect(assign).toHaveBeenCalledWith("/login?next=%2Fapp%2Fanalyses%2F1");
  });
});
