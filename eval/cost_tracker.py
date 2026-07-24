# -*- coding: utf-8 -*-
"""Phase 1 cost tracker — MEASURED tokens x REAL rates. No estimates.

The dollar figure is computed entirely from tokens that were actually billed:
each trajectory .jsonl records per-step ``tokens_in`` / ``tokens_out`` (the SDK's
usage.prompt_tokens/completion_tokens for OpenAI-compatible, input_tokens/
output_tokens for Anthropic — image/vision tokens are already included in these).

    cost = SUM over tiers, SUM over that tier's trajectory files, SUM over steps of
              step.tokens_in  * RATE_IN[tier]
            + step.tokens_out * RATE_OUT[tier]

Tier is determined by which subdirectory a trajectory lives in (the cascade writes
one dir per model tier: qwen/ gpt-5.1/ gpt-5.5/ sonnet/), so a trajectory is billed
at the rate of the model that produced it.

RATES ($ per token) — verified 2026-07-02, STANDARD/synchronous tier (our agents call
chat.completions/messages in real time, NOT the 50%-off Batch API):
  * qwen  — OpenRouter live API (we bill Qwen through OpenRouter exactly): $0.20 / $0.88
  * gpt-5.1 — OpenRouter API (openai/gpt-5.1 = prompt 0.00000125 / completion 0.00001)
              AND web pricing guide both give $1.25 / $10.00. NOTE: $0.625 / $5.00 is the
              OpenAI *Batch API* price (flat 50% off) — not applicable, we call sync.
  * gpt-5.5 — OpenAI official pricing page + OpenRouter agree: $5.00 / $30.00
  * gpt-5.6-sol — OpenAI GPT-5.6 Sol tier, standard short-context: $5.00 / $30.00
              (verified 2026-07-09 against developers.openai.com pricing + multiple
              trackers; cached-in $0.50/M, long-context $10/$45 — not used, we call
              sync short-context). Same headline rate as gpt-5.5 but billed as its
              OWN tier so per-model attribution stays clean.
  * hy3 — OpenRouter paid tencent/hy3: $0.14 / $0.58
  * hy3-free — OpenRouter tencent/hy3:free: $0.00 / $0.00
  * sonnet  — Anthropic Sonnet-4.6 tier: $3.00 / $15.00
Override any via env (e.g. RATE_GPT51_IN=0.625 if you switch to the Batch API).
"""
import glob
import json
import os
import sys

# $/million tokens (converted to $/token below). Real, sourced rates.
_DEFAULT_RATES_PER_M = {
    "qwen":        {"in": 0.20, "out": 0.88},
    "gpt-5.1":     {"in": 1.25, "out": 10.00},
    "gpt-5.5":     {"in": 5.00, "out": 30.00},
    "gpt-5.6-sol": {"in": 5.00, "out": 30.00},
    "hy3":          {"in": 0.14, "out": 0.58},
    "hy3-free":     {"in": 0.00, "out": 0.00},
    "sonnet":      {"in": 3.00, "out": 15.00},
    # Opus 4.8 STANDARD short-context (verified 2026-07-09 against Anthropic's
    # pricing page + launch post): $5.00 / $25.00. NOT $15/$75 (an old wrong
    # assumption). Caveats NOT applied here (we call standard, non-geo, uncached):
    # fast-mode = 2x ($10/$50), inference_geo=US = 1.1x, prompt-caching = up to -90%.
    # Billed as its OWN tier so Opus is never silently mibilled as sonnet ($3/$15).
    "opus":        {"in": 5.00, "out": 25.00},
    # Gemini 3.1 Pro list (≤200k context): $2 / $12 per MTok (CURRENT_WORK §G).
    "gemini":      {"in": 2.00, "out": 12.00},
}
_ENV = {"qwen": "QWEN", "gpt-5.1": "GPT51", "gpt-5.5": "GPT55",
        "gpt-5.6-sol": "GPT56SOL", "hy3": "HY3", "hy3-free": "HY3FREE",
        "sonnet": "SONNET", "opus": "OPUS", "gemini": "GEMINI"}


def rates_per_token():
    out = {}
    for tier, r in _DEFAULT_RATES_PER_M.items():
        e = _ENV[tier]
        rin = float(os.getenv(f"RATE_{e}_IN", r["in"])) / 1e6
        rout = float(os.getenv(f"RATE_{e}_OUT", r["out"])) / 1e6
        out[tier] = {"in": rin, "out": rout}
    return out


def tier_tokens(traj_dir):
    """Sum MEASURED tokens_in/out over every trajectory in a tier dir. Returns
    (tokens_in, tokens_out, n_episodes, n_retry_flagged)."""
    tin = tout = n = retried = 0
    for f in glob.glob(os.path.join(traj_dir, "*.jsonl")):
        if f.endswith("_scorecard.json"):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        n += 1
        for s in (d.get("steps") or []):
            tin += int(s.get("tokens_in") or 0)
            tout += int(s.get("tokens_out") or 0)
        # a recorded agent error containing our guard's signature = a call that
        # exhausted retries (worth surfacing per the plan's retry watch)
        if "LLMCallError" in (d.get("error") or ""):
            retried += 1
    return tin, tout, n, retried


def _tier_from_agent(agent_name):
    """Infer the billing tier from the trajectory's agent_name (the model that
    produced it), NOT from its directory. Layout-independent — works for flat
    single-run dirs AND sharded parallel dirs. Returns None if unrecognized."""
    a = (agent_name or "").lower()
    if "gemini" in a:
        return "gemini"
    if "qwen" in a:
        return "qwen"
    if "tencent/hy3:free" in a:
        return "hy3-free"
    if "tencent/hy3" in a:
        return "hy3"
    # opus BEFORE sonnet/claude — an Opus agent_name is "pixel[claude-opus-4-8]",
    # which contains BOTH "opus" AND "claude". Matching "claude"->sonnet first would
    # bill Opus at the sonnet rate ($3/$15 instead of $5/$25) — a silent ~1.7x
    # under-count, the same misbilling class fixed for gpt-5.6-sol.
    if "opus" in a:
        return "opus"
    if "sonnet" in a or "claude" in a:
        return "sonnet"
    # 5.6 BEFORE 5.5/5.1 — distinct substrings, but keep the newest tier explicit so
    # an openai_pixel[gpt-5.6-sol] episode bills as its OWN tier (was returning None ->
    # silently skipped -> $0, which would have made WS2's per-episode spend fake).
    if "5.6" in a:
        return "gpt-5.6-sol"
    if "5.5" in a:
        return "gpt-5.5"
    if "5.1" in a:
        return "gpt-5.1"
    return None


def cost_of_tree(root, cap=None, verbose=True):
    """Layout-INDEPENDENT cost: recurse over EVERY *.jsonl under ``root`` and bill
    each episode at the rate of the model that produced it (from agent_name). This
    is the correct primitive for BOTH a flat single-run dir (root/qwen/*.jsonl) and
    a sharded parallel dir (root/shard_N/<tier>/*.jsonl). The earlier dir-keyed
    cost_report() silently returned $0 for sharded layouts because root/qwen did not
    exist — which is exactly how the live tracker under-counted and how the per-shard
    cap check went blind to global spend.

    Returns (total_cost, rows) where rows = [(tier, n, tin, tout, cost, retried)]."""
    rates = rates_per_token()
    agg = {t: [0, 0, 0, 0] for t in _DEFAULT_RATES_PER_M}   # tin, tout, n, retried
    for f in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        if f.endswith("_scorecard.json"):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue                                          # partial/in-flight write — skip
        tier = _tier_from_agent(d.get("agent_name"))
        if tier is None:
            continue
        agg[tier][2] += 1
        for s in (d.get("steps") or []):
            agg[tier][0] += int(s.get("tokens_in") or 0)
            agg[tier][1] += int(s.get("tokens_out") or 0)
        if "LLMCallError" in (d.get("error") or ""):
            agg[tier][3] += 1
    total = 0.0
    rows = []
    for tier, (tin, tout, n, retried) in agg.items():
        c = tin * rates[tier]["in"] + tout * rates[tier]["out"]
        total += c
        rows.append((tier, n, tin, tout, c, retried))
    if verbose:
        print(f"{'tier':<9} {'eps':>4} {'tokens_in':>13} {'tokens_out':>12} "
              f"{'$in/M':>7} {'$out/M':>7} {'cost$':>9} {'retry!':>6}")
        print("-" * 78)
        for tier, n, tin, tout, c, retried in rows:
            rm = _DEFAULT_RATES_PER_M[tier]
            print(f"{tier:<9} {n:>4} {tin:>13,} {tout:>12,} "
                  f"{rm['in']:>7.2f} {rm['out']:>7.2f} {c:>9.2f} {retried:>6}")
        print("-" * 78)
        print(f"{'TOTAL':<9} {sum(r[1] for r in rows):>4} "
              f"{sum(r[2] for r in rows):>13,} {sum(r[3] for r in rows):>12,} "
              f"{'':>7} {'':>7} {total:>9.2f}")
        if cap is not None:
            pct = 100.0 * total / cap if cap else 0
            print(f"\nbudget cap ${cap:.0f} — spent ${total:.2f} ({pct:.1f}%)"
                  + ("  *** OVER CAP — STOP ***" if total >= cap else ""))
    return total, rows


def cost_report(run_dir, tier_dirs=None, cap=None):
    """run_dir contains per-tier subdirs. tier_dirs optionally overrides the
    {tier: path} mapping (used to bill an arbitrary dir at a tier's rate).

    NOTE: this is the DIRECTORY-keyed report — it only sees flat root/<tier>/ dirs
    and returns $0 for sharded layouts. For a correct, layout-independent total
    (and for any live cap check), use cost_of_tree() instead."""
    rates = rates_per_token()
    if tier_dirs is None:
        tier_dirs = {t: os.path.join(run_dir, t) for t in _DEFAULT_RATES_PER_M}
    rows = []
    total = 0.0
    for tier, path in tier_dirs.items():
        if not os.path.isdir(path):
            continue
        tin, tout, n, retried = tier_tokens(path)
        c = tin * rates[tier]["in"] + tout * rates[tier]["out"]
        total += c
        rows.append((tier, n, tin, tout, c, retried))

    print(f"{'tier':<9} {'eps':>4} {'tokens_in':>13} {'tokens_out':>12} "
          f"{'$in/M':>7} {'$out/M':>7} {'cost$':>9} {'retry!':>6}")
    print("-" * 78)
    for tier, n, tin, tout, c, retried in rows:
        rm = _DEFAULT_RATES_PER_M[tier]
        print(f"{tier:<9} {n:>4} {tin:>13,} {tout:>12,} "
              f"{rm['in']:>7.2f} {rm['out']:>7.2f} {c:>9.2f} {retried:>6}")
    print("-" * 78)
    print(f"{'TOTAL':<9} {sum(r[1] for r in rows):>4} "
          f"{sum(r[2] for r in rows):>13,} {sum(r[3] for r in rows):>12,} "
          f"{'':>7} {'':>7} {total:>9.2f}")
    if cap is not None:
        pct = 100.0 * total / cap if cap else 0
        print(f"\nbudget cap ${cap:.0f} — spent ${total:.2f} ({pct:.1f}%)"
              + ("  *** OVER CAP — STOP ***" if total >= cap else ""))
    return total, rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True,
                    help="dir containing per-tier subdirs (qwen/ gpt-5.1/ gpt-5.5/ sonnet/)")
    ap.add_argument("--cap", type=float, default=500.0)   # budget cap (USD)
    ap.add_argument("--bill-as", default=None,
                    help="debug: bill a single dir at a tier rate, e.g. sonnet:/tmp/x")
    args = ap.parse_args()
    if args.bill_as:
        tier, path = args.bill_as.split(":", 1)
        total, _ = cost_report(args.run_dir, tier_dirs={tier: path}, cap=args.cap)
    else:
        total, _ = cost_report(args.run_dir, cap=args.cap)
    sys.exit(2 if (args.cap and total >= args.cap) else 0)
