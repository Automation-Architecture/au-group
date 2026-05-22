# Playwright E2E (AU Group)

Browser and API checks for the **document-parser** service.

## Local run

1. Start the parser with OpenAPI enabled:

```bash
cd services/document-parser
EXPOSE_OPENAPI=true ./scripts/dev.sh
```

2. In another terminal:

```bash
cd e2e
npm install
npx playwright install chromium
PARSER_BASE_URL=http://127.0.0.1:8001 npm test
```

## Against staging / production

```bash
PARSER_BASE_URL=https://your-parser.up.railway.app npm test
```

`/health/ready` may return **503** when Supabase/S3 are unset — tests allow 200 or 503.

## CI

Runs in [`.github/workflows/ci-playwright.yml`](../.github/workflows/ci-playwright.yml) (starts parser on `127.0.0.1:8001` in the job). Also optional in [`smoke-e2e.yml`](../.github/workflows/smoke-e2e.yml) when `PARSER_BASE_URL` is set.
