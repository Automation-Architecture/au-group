# n8n-skills in CI/CD

Deterministic workflow linting based on [czlonkowski/n8n-skills](https://github.com/czlonkowski/n8n-skills) — the Claude Code skillset for building n8n workflows with [n8n-mcp](https://github.com/czlonkowski/n8n-mcp).

## Two layers

| Layer | Where | What |
|-------|--------|------|
| **CI (deterministic)** | `ci-n8n.yml` | Python rules from skill content → `n8n-reports/n8n-skills-lint.json` |
| **Agent skills (optional)** | Cursor / Claude | Full 7 skills for authoring — install from upstream repo |

CI does **not** run Claude or MCP validate loops; it applies fixed rules aligned with the skills.

## CI behavior

- **Trigger:** `workflows/**` path filter (with other n8n CI files)
- **Pin:** [`.n8n-skills-ref`](../../.n8n-skills-ref) or repo variable `N8N_SKILLS_REF`
- **Scope:** `workflows/manifest.yaml` CD JSON + all `workflows/pulled/*.json`
- **Fail:** Any finding with severity `ERROR`
- **Warn:** Logged in report artifact (e.g. webhook `$json.body` hints) — does not fail CI

## Rule mapping (skills → CI)

| Skill | CI rule IDs |
|-------|-------------|
| [n8n-expression-syntax](https://github.com/czlonkowski/n8n-skills/tree/main/skills/n8n-expression-syntax) | `EXPR-TRIPLE-BRACE`, `EXPR-WEBHOOK-BODY`, `EXPR-SINGLE-BRACE`, `EXPR-NODE-REF` |
| [n8n-code-javascript](https://github.com/czlonkowski/n8n-skills/tree/main/skills/n8n-code-javascript) | `CODE-JS-NO-RETURN`, `CODE-JS-NO-EXPR-SYNTAX`, `CODE-JS-WEBHOOK-BODY` |
| [n8n-code-python](https://github.com/czlonkowski/n8n-skills/tree/main/skills/n8n-code-python) | `CODE-PY-FORBIDDEN-IMPORT` |
| [n8n-validation-expert](https://github.com/czlonkowski/n8n-skills/tree/main/skills/n8n-validation-expert) | `JSON-INVALID` |

Implementation: [`scripts/ci/n8n_skills_linter.py`](../../scripts/ci/n8n_skills_linter.py)

## Local commands

```bash
python3 scripts/ci/validate-n8n-skills.py
python3 scripts/ci/n8n_skills_linter.py --report n8n-reports/n8n-skills-lint.json
```

## Install skills in Cursor (authoring)

```bash
/plugin install czlonkowski/n8n-skills
# or: git clone https://github.com/czlonkowski/n8n-skills && cp -r skills/* ~/.claude/skills/
```

Use with existing project **n8n-mcp** (`.cursor/mcp.json`).

## Related

- [`workflows/README.md`](../../workflows/README.md) — pull + manifest CI
- [`requirements-traceability.md`](requirements-traceability.md) — AU_GROUP-8
