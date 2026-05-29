-- Remove legacy (uuid, jsonb) overload so calls resolve to KD-40 (uuid, jsonb, numeric).
-- Without this, PERFORM/RPC with two args errors: "function ... is not unique".

drop function if exists public.au_group_merge_creditor_matrix(uuid, jsonb);
