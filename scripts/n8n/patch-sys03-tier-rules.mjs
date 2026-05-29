#!/usr/bin/env node
/**
 * KD-21: Patch SYS-03 Creditor Enrichment (j26cimQ4S7kN67IP) to use Supabase tier RPCs.
 *
 * Usage:
 *   N8N_API_URL=https://automationarchitecture.app.n8n.cloud N8N_API_KEY=... \
 *     node scripts/n8n/patch-sys03-tier-rules.mjs --push
 *
 * Dry-run (writes workflows/pulled/sys-03-tier-patched.json):
 *   node scripts/n8n/patch-sys03-tier-rules.mjs
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const WORKFLOW_ID = 'j26cimQ4S7kN67IP';
const TARGET_NODE_NAMES = ['ZoomInfo Enrich Company', 'ZoomInfo Enrich Company1'];
const HELPERS_MARKER_START = '// KD-21 TIER RPC HELPERS START';
const HELPERS_MARKER_END = '// KD-21 TIER RPC HELPERS END';
const LEGACY_TIER_PATTERNS = [
  /const\s+TIER_TITLES\s*=\s*\{[\s\S]*?\};/g,
  /const\s+TIER_1_TITLES[\s\S]*?const\s+TIER_3_TITLES[\s\S]*?;/g,
  /function\s+classifyCompanyTier\s*\([^)]*\)\s*\{[\s\S]*?\n\}/g,
  /function\s+classifyTier\s*\([^)]*\)\s*\{[\s\S]*?\n\}/g,
  /function\s+getTargetTitles\s*\([^)]*\)\s*\{[\s\S]*?\n\}/g,
];

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..');
const HELPERS_PATH = join(__dirname, 'lib', 'sys03-tier-rpc-helpers.js');
const OUT_PATH = join(ROOT, 'workflows', 'pulled', 'sys-03-tier-patched.json');

const push = process.argv.includes('--push');

function resolveN8nConfig() {
  const baseUrl = (
    process.env.N8N_API_URL ||
    process.env.N8N_BASE_URL ||
    'https://automationarchitecture.app.n8n.cloud'
  ).replace(/\/$/, '');
  const apiKey = process.env.N8N_API_KEY;
  if (push && !apiKey) {
    throw new Error('N8N_API_KEY required for --push');
  }
  return { baseUrl, apiKey };
}

async function fetchWorkflow(baseUrl, apiKey) {
  const res = await fetch(`${baseUrl}/api/v1/workflows/${WORKFLOW_ID}`, {
    headers: { 'X-N8N-API-KEY': apiKey },
  });
  if (!res.ok) {
    throw new Error(`GET workflow ${WORKFLOW_ID} failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

async function putWorkflow(baseUrl, apiKey, workflow) {
  const body = {
    name: workflow.name,
    nodes: workflow.nodes,
    connections: workflow.connections,
    settings: workflow.settings,
    staticData: workflow.staticData,
  };
  const res = await fetch(`${baseUrl}/api/v1/workflows/${WORKFLOW_ID}`, {
    method: 'PUT',
    headers: {
      'X-N8N-API-KEY': apiKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`PUT workflow ${WORKFLOW_ID} failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

function loadHelpersBlock() {
  const raw = readFileSync(HELPERS_PATH, 'utf8');
  return `${HELPERS_MARKER_START}\n${raw}\n${HELPERS_MARKER_END}`;
}

function stripLegacyTierBlock(jsCode) {
  let next = jsCode;
  for (const pattern of LEGACY_TIER_PATTERNS) {
    next = next.replace(pattern, '');
  }
  return next;
}

function injectHelpers(jsCode, helpersBlock) {
  const start = jsCode.indexOf(HELPERS_MARKER_START);
  const end = jsCode.indexOf(HELPERS_MARKER_END);
  if (start !== -1 && end !== -1) {
    return `${jsCode.slice(0, start)}${helpersBlock}\n${jsCode.slice(end + HELPERS_MARKER_END.length)}`;
  }
  return `${helpersBlock}\n\n${jsCode}`;
}

function patchTierUsage(jsCode) {
  let next = jsCode;

  // Replace inline tier classification with RPC-backed resolver when present.
  next = next.replace(
    /const\s+assignedTier\s*=\s*classify(?:Company)?Tier\s*\([^)]*\)\s*;?/g,
    `const bankruptcyId = $json.bankruptcy_id ?? null;
const tierTargeting = await resolveTierTargeting.call(this, companyRevenue, companyEmployees, creditorId, bankruptcyId);
const assignedTier = tierTargeting.assigned_tier;
const tierTitlesMap = tierTargeting.tier_titles_map;
const targetTitles = tierTargeting.target_titles;
const tierName = tierTargeting.tier_name;`,
  );

  next = next.replace(
    /const\s+tierTitlesMap\s*=\s*\{[\s\S]*?\};/g,
    '// tierTitlesMap loaded via resolveTierTargeting (KD-21)',
  );

  next = next.replace(
    /const\s+targetTitles\s*=\s*TIER_TITLES\[assignedTier\][^;]*;?/g,
    '// targetTitles from resolveTierTargeting (KD-21)',
  );

  if (!next.includes('resolveTierTargeting.call')) {
    next = next.replace(
      /(const\s+companyRevenue\s*=[^;]+;[\s\S]*?const\s+companyEmployees\s*=[^;]+;)/,
      `$1
const bankruptcyId = $json.bankruptcy_id ?? null;
const tierTargeting = await resolveTierTargeting.call(this, companyRevenue, companyEmployees, creditorId, bankruptcyId);
const assignedTier = tierTargeting.assigned_tier;
const tierTitlesMap = tierTargeting.tier_titles_map;
const targetTitles = tierTargeting.target_titles;
const tierName = tierTargeting.tier_name;`,
    );
  }

  return next;
}

function patchWorkflow(workflow) {
  const helpersBlock = loadHelpersBlock();
  let patched = 0;

  for (const node of workflow.nodes) {
    if (!TARGET_NODE_NAMES.includes(node.name)) continue;
    if (node.type !== 'n8n-nodes-base.code') continue;

    const before = node.parameters?.jsCode ?? '';
    if (!before.trim()) {
      console.warn(`skip ${node.name}: empty jsCode`);
      continue;
    }

    let jsCode = stripLegacyTierBlock(before);
    jsCode = injectHelpers(jsCode, helpersBlock);
    jsCode = patchTierUsage(jsCode);

    if (jsCode === before) {
      console.warn(`${node.name}: no tier usage patterns matched — helpers injected only`);
    }

    node.parameters.jsCode = jsCode;
    if (!node.credentials?.httpHeaderAuth) {
      node.credentials = {
        ...(node.credentials ?? {}),
        httpHeaderAuth: { name: 'AU Group Supabase Service Role' },
      };
    }
    patched += 1;
  }

  if (patched === 0) {
    throw new Error(`No target Code node found (${TARGET_NODE_NAMES.join(', ')})`);
  }

  return workflow;
}

async function main() {
  const { baseUrl, apiKey } = resolveN8nConfig();
  const helpersBlock = loadHelpersBlock();
  console.log(`Loaded KD-21 helpers (${helpersBlock.split('\n').length} lines)`);

  let workflow;
  if (push) {
    workflow = await fetchWorkflow(baseUrl, apiKey);
  } else if (process.env.N8N_API_KEY) {
    workflow = await fetchWorkflow(baseUrl, apiKey);
  } else {
    console.log('No N8N_API_KEY — writing snippet-only artifact; use --push after setting credentials.');
    mkdirSync(dirname(OUT_PATH), { recursive: true });
    writeFileSync(
      OUT_PATH,
      JSON.stringify(
        {
          workflow_id: WORKFLOW_ID,
          patch: 'KD-21 tier RPC helpers',
          helpers_file: 'scripts/n8n/lib/sys03-tier-rpc-helpers.js',
          target_nodes: TARGET_NODE_NAMES,
          note: 'Run with N8N_API_KEY to fetch live workflow and patch',
        },
        null,
        2,
      ),
    );
    console.log(`Wrote ${OUT_PATH}`);
    return;
  }

  const patched = patchWorkflow(workflow);
  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, JSON.stringify(patched, null, 2));
  console.log(`Wrote ${OUT_PATH}`);

  if (push) {
    await putWorkflow(baseUrl, apiKey, patched);
    console.log(`Pushed KD-21 tier patch to ${WORKFLOW_ID}`);
  } else {
    console.log('Dry-run complete (fetched + patched locally). Re-run with --push to deploy.');
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
