import { test, expect } from "@playwright/test";

test.describe("document-parser OpenAPI (EXPOSE_OPENAPI=true)", () => {
  test.beforeAll(async ({ request }, testInfo) => {
    const response = await request.get("/openapi.json");
    testInfo.skip(
      response.status() === 404,
      "OpenAPI disabled (EXPOSE_OPENAPI=false) — skip UI tests",
    );
  });
  test("openapi.json lists API paths", async ({ request }) => {
    const response = await request.get("/openapi.json");
    expect(response.ok()).toBeTruthy();
    const spec = await response.json();
    expect(spec.info?.title).toContain("Document Parser");
    expect(spec.paths).toBeDefined();
    expect(spec.paths["/health"]).toBeDefined();
  });

  test("Swagger UI loads at /docs", async ({ page }) => {
    const response = await page.goto("/docs");
    expect(response?.ok()).toBeTruthy();
    await expect(page.locator("#swagger-ui")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("AU Group Document Parser")).toBeVisible();
  });
});
