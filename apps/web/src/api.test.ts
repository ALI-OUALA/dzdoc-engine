import { afterEach, describe, expect, it, vi } from "vitest";
import { DzDocClient } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("DzDocClient", () => {
  it("keeps the API key in the authorization header", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await new DzDocClient("secret", "https://dzdoc.test").listJobs();
    expect(fetchMock).toHaveBeenCalledWith(
      "https://dzdoc.test/v1/jobs",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer secret" }) }),
    );
  });

  it("surfaces API errors without hiding the server detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid API key" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(new DzDocClient("bad", "https://dzdoc.test").listJobs()).rejects.toThrow(
      "invalid API key",
    );
  });
});
