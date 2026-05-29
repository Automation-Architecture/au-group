// KD-21: Supabase tier RPC helpers — injected into SYS-03 "ZoomInfo Enrich Company" Code node.
// Do not edit in n8n UI; change this file and run patch-sys03-tier-rules.mjs --push.
// Security: service_role via httpHeaderAuth only; never log Authorization/apikey headers.

function resolveSupabaseConfig() {
  const configNode =
    $('Config supabase').first()?.json ?? $('Config — Supabase').first()?.json ?? {};
  const baseUrl = String(configNode.project_url ?? configNode.supabase_url ?? '').replace(/\/?$/, '/');
  if (!baseUrl) {
    throw new Error('KD-21 tier RPC: Config supabase must set project_url or supabase_url');
  }
  return { baseUrl };
}

function rpcResultToBoolean(result) {
  if (result === true) return true;
  if (result === false) return false;
  if (Array.isArray(result)) {
    const first = result[0];
    return first === true || first === 'true';
  }
  return false;
}

async function auGroupSupabaseRpc(rpcName, body) {
  const { baseUrl } = resolveSupabaseConfig.call(this);
  const cred = await this.getCredentials('httpHeaderAuth');
  const apiKey = cred.value;
  if (!apiKey) {
    throw new Error('KD-21 tier RPC: missing httpHeaderAuth credential (AU Group Supabase Service Role)');
  }
  return this.helpers.httpRequest({
    method: 'POST',
    url: `${baseUrl}rpc/${rpcName}`,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      apikey: apiKey,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
    },
    body,
    json: true,
  });
}

async function loadTierTargetingConfig() {
  const raw = await auGroupSupabaseRpc.call(this, 'au_group_get_tier_targeting_config', {});
  const config = raw && typeof raw === 'object' ? raw : {};
  if (!Array.isArray(config.tiers) || config.tiers.length === 0) {
    throw new Error('au_group_get_tier_targeting_config returned no tiers');
  }
  return config;
}

function titlesForTier(config, tier) {
  const tierNum = Number(tier);
  const entry = config.tiers.find((t) => Number(t.tier) === tierNum);
  if (!entry || !Array.isArray(entry.titles)) return [];
  return entry.titles.filter((t) => typeof t === 'string' && t.trim() !== '');
}

async function classifyCompanyTier(revenue, employees) {
  const rows = await auGroupSupabaseRpc.call(this, 'au_group_classify_company_tier', {
    p_revenue: revenue ?? null,
    p_employees: employees ?? null,
  });
  const row = Array.isArray(rows) ? rows[0] : rows;
  if (!row || row.tier == null) {
    throw new Error(
      `au_group_classify_company_tier returned no tier (revenue=${revenue}, employees=${employees})`,
    );
  }
  const tier = Number(row.tier);
  if (!Number.isFinite(tier) || tier < 1 || tier > 3) {
    throw new Error(`au_group_classify_company_tier returned invalid tier: ${row.tier}`);
  }
  return {
    tier,
    tier_name: row.tier_name ?? 'smb',
    matched_on: row.matched_on ?? null,
    min_revenue: row.min_revenue ?? null,
    min_employees: row.min_employees ?? null,
  };
}

async function persistCreditorCompanyTier(creditorId, tier, bankruptcyId) {
  if (!creditorId || !tier) return false;
  const body = {
    p_creditor_id: creditorId,
    p_tier: tier,
  };
  if (bankruptcyId) {
    body.p_bankruptcy_id = bankruptcyId;
  }
  const result = await auGroupSupabaseRpc.call(this, 'au_group_set_creditor_company_tier', body);
  return rpcResultToBoolean(result);
}

async function resolveTierTargeting(revenue, employees, creditorId, bankruptcyId) {
  const classification = await classifyCompanyTier.call(this, revenue, employees);
  const config = await loadTierTargetingConfig.call(this);
  const assignedTier = classification.tier;
  const targetTitles = titlesForTier(config, assignedTier);
  const tierTitlesMap = {};
  for (let t = assignedTier; t <= 3; t += 1) {
    tierTitlesMap[t] = titlesForTier(config, t);
  }
  if (creditorId) {
    const persisted = await persistCreditorCompanyTier.call(
      this,
      creditorId,
      assignedTier,
      bankruptcyId ?? null,
    );
    if (!persisted) {
      throw new Error(
        `au_group_set_creditor_company_tier failed (creditor=${creditorId}, tier=${assignedTier}, bankruptcy=${bankruptcyId ?? 'none'})`,
      );
    }
  }
  return {
    assigned_tier: assignedTier,
    tier_name: classification.tier_name,
    tier_matched_on: classification.matched_on,
    target_titles: targetTitles,
    tier_titles_map: tierTitlesMap,
  };
}
