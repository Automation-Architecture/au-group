import { test, expect } from "@playwright/test";

const apiKey =
  process.env.API_KEY ?? "test-api-key-for-ci-suite-only-do-not-use-in-production";

test.describe("document-parser parse API flow", () => {
  test("POST /api/v1/parse/structured requires authentication", async ({
    request,
  }) => {
    const response = await request.post("/api/v1/parse/structured", {
      data: { s3_key: "raw-documents/24-10001/doc.pdf" },
    });
    expect(response.status()).toBe(403);
  });

  test("authenticated parse/structured validates request body", async ({
    request,
  }) => {
    const response = await request.post("/api/v1/parse/structured", {
      headers: { "X-API-Key": apiKey },
      data: {},
    });
    expect(response.status()).toBe(400);
    const body = await response.json();
    expect(body.detail).toBe("Invalid request");
  });

  test("authenticated parse/structured rejects unsafe s3_key", async ({
    request,
  }) => {
    const response = await request.post("/api/v1/parse/structured", {
      headers: { "X-API-Key": apiKey },
      data: { s3_key: "../etc/passwd" },
    });
    expect([400, 422]).toContain(response.status());
  });

  test("returns X-Request-ID and accepts client correlation header", async ({
    request,
  }) => {
    const correlationId = "e2e-correlation-test-id";
    const response = await request.get("/health", {
      headers: { "X-Request-ID": correlationId },
    });
    expect(response.ok()).toBeTruthy();
    expect(response.headers()["x-request-id"]).toBe(correlationId);
  });

  test("openapi documents parse routes", async ({ request }, testInfo) => {
    const response = await request.get("/openapi.json");
    testInfo.skip(
      response.status() === 404,
      "OpenAPI disabled (EXPOSE_OPENAPI=false)",
    );
    expect(response.ok()).toBeTruthy();
    const spec = await response.json();
    expect(spec.paths["/api/v1/parse/structured"]).toBeDefined();
    expect(spec.paths["/api/v1/parse/document"]).toBeDefined();
    expect(spec.paths["/api/v1/parse/ocr"]).toBeDefined();
  });
});
