import { test, expect } from "@playwright/test";

test.describe("document-parser health", () => {
  test("GET /health returns ok", async ({ request }) => {
    const response = await request.get("/health");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe("ok");
    expect(body.parser_version).toBeTruthy();
  });

  test("GET /health/ready returns checks object", async ({ request }) => {
    const response = await request.get("/health/ready");
    expect([200, 503]).toContain(response.status());
    const body = await response.json();
    expect(body).toHaveProperty("checks");
    expect(body).toHaveProperty("parser_version");
  });
});
