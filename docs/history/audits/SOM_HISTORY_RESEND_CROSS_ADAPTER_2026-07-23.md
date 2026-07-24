# SoM full-screenshot-history-resend: harness-wide vs Gemini-specific (2026-07-23)

## Verdict

**Harness-wide — not Gemini-specific.**

Every SoM (and coord) pixel loop appends a new screenshot each turn and
re-sends the **full** `messages` / `input_items` history on the next LLM call.
There is **no** “keep last K frames” truncation in any adapter. The only
history-related control is `LLM_CONTEXT_BUDGET`: when measured
`prompt_tokens` / `input_tokens` of the previous turn meet the budget, the
episode **ends** (INCOMPLETE), leaving prior frames still billed for every
turn up to that point.

Gemini merely **inherits** `OpenAIPixelAgent` and is usually run with a much
larger budget (`900000`) and step cap (`120`), so thrash episodes accumulate
more triangular cost — same mechanism, longer runway.

Related: `docs/history/audits/GEMINI_SOM_TOKEN_GROWTH_AND_STEP60_2026-07-23.md`
(Gemini-only measurement). This note confirms the same pattern across Qwen /
GPT-5.1 / GPT-5.5 / Sol / Sonnet / Opus trajs.

---

## Code map

### Inheritance

| Agent kind | Class | Loop implementation |
|------------|--------|---------------------|
| `openai_pixel` (GPT-5.1 / 5.5 / …) | `OpenAIPixelAgent` | Own `run()` + `_run_responses()` |
| `qwen` | `QwenAgent(OpenAIPixelAgent)` | **Inherits** openai_pixel loop (endpoint/model only) |
| `gemini` | `GeminiPixelAgent(OpenAIPixelAgent)` | **Inherits** openai_pixel loop (endpoint/model only) |
| `pixel` (Sonnet / Opus / Haiku) | `PixelBrowserAgent` | **Parallel reimplementation** — same append-all pattern |
| `openai_coord` / `pixel_coord` | coord agents | Same append-all screenshots (no SoM marks) |

`agents/gemini_pixel_agent.py`:

> Thin specialisation of `OpenAIPixelAgent` … Same SoM perception, multi-tab
> tools, `eval_mode`, and dynamic context guard as the Qwen / openai_pixel agents.

`agents/qwen_agent.py`: same subclass pattern (DashScope / OpenRouter URL + key).

### Full history resend (no keep-last-K)

**OpenAI-compat path** (`agents/openai_pixel_agent.py`):

```177:237:agents/openai_pixel_agent.py
        # DYNAMIC context guard: the pixel loop re-sends every prior screenshot, so
        # context grows unbounded and eventually 400s past the model's window
        # (Qwen3-VL = 131072). Rather than a fixed step cap (a task-dependent proxy),
        # end the episode gracefully once the MEASURED prompt_tokens of a turn nears
        # the window — task-adaptive (dense pages stop sooner) and per-model (set
        # LLM_CONTEXT_BUDGET per tier; default 190000 leaves headroom for Sonnet 200K
        # / gpt-5.x, and the cascade sets 118000 for the Qwen tier).
        self.context_budget = int(os.getenv("LLM_CONTEXT_BUDGET", "190000"))
        ...
            messages.append({"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}",
                               "detail": "high"}},
            ]})
```

Each turn appends a `detail: "high"` SoM image; `messages=` is passed whole to
`chat.completions.create`. Never sliced.

**Responses API path** (gpt-5.6-sol / models that need `/v1/responses`) — same
append-all on `input_items`, including `detail: "high"` images
(`_run_responses`, ~L399–434).

**Anthropic pixel path** (`agents/pixel_agent.py`):

```419:484:agents/pixel_agent.py
        # DYNAMIC context guard (see openai_pixel_agent) — end the episode before the
        # accumulated screenshots overflow the model window, using measured
        # input_tokens. Default 190000 (Sonnet 4.6 = 200K); per-tier via env.
        self.context_budget = int(os.getenv("LLM_CONTEXT_BUDGET", "190000"))
        ...
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            })
            ...
            messages.append({"role": "user", "content": content_blocks})
```

Opus vs Sonnet only changes thinking kwargs (`adaptive` vs `budget_tokens`);
message history handling is shared.

**Search confirmation:** no `keep last`, message-window prune, `max_images`, or
`messages = messages[-K:]` under `agents/` / `harness/` for these loops.

### What *does* differ by adapter: episode stop, not history trim

| Surface | Typical `LLM_CONTEXT_BUDGET` | Typical `AGENT_MAX_STEPS` | Effect on history |
|---------|------------------------------|---------------------------|-------------------|
| Cascade Qwen | **60000** (`eval/cascade_v2.py` `CONTEXT_BUDGET`) | 120 backstop | Stops earlier → fewer frames ever accumulated |
| Cascade GPT-5.1 / 5.5 / Sonnet | **190000** | 120 | Can grow until ~window or step cap |
| Gemini Cloud Run / pilots | **900000** | 120 (or 60 subsample) | Longest runway; thrash ≈ `N²` to step 120 |
| Default in agent `__init__` | 190000 | 50 | Used when env unset |

Stopping the episode ≠ truncating history. Until stop, every prior SoM frame is
re-billed.

---

## Per-adapter summary

| Family | Agent entry | History resend? | History truncation? | Context stop? |
|--------|-------------|-----------------|---------------------|---------------|
| Qwen | `QwenAgent` → openai_pixel | Yes (`detail=high`) | No | Yes (cascade often 60k) |
| GPT-5.1 / 5.5 | `OpenAIPixelAgent` | Yes | No | Yes (190k) |
| GPT-5.6-sol | openai_pixel `_run_responses` | Yes | No | Yes (190k default) |
| Gemini | `GeminiPixelAgent` → openai_pixel | Yes (identical loop) | No | Yes (often 900k) |
| Sonnet | `PixelBrowserAgent` | Yes | No | Yes (190k) |
| Opus | same pixel agent, opus thinking branch | Yes | No | Yes (190k) |
| Coord (non-SoM) | pixel_coord / openai_coord | Yes (plain shots) | No | Coord Anthropic path historically weaker / absent guard |

---

## Trajectory evidence (read-only sampling)

Method: `.venv/bin/python` over pretty-JSON `*.jsonl` under
`trajectories/` (main repo) and
`ecommerce-browser-gym-sonnet-completions/trajectories/`. Per-step
`tokens_in` from `StepRecord` (provider-reported prompt/input tokens, vision
included — see `eval/cost_tracker.py`).

Quadratic signature: if each new SoM frame adds ~`c` tokens and all prior
frames are resent, then `tokens_in(step k) ≈ c·(k+1)` and
`sum_tokens ≈ c·N(N+1)/2`. Correlation of `tokens_in` with step index ≈ 1.0
on long episodes across families.

### Long-episode growth (`n_steps ≥ 40`, sampled corpus)

| Family | n long eps | mean N | median fitted `c` | median corr(step, tin) | median late/early third |
|--------|----------:|-------:|------------------:|-----------------------:|------------------------:|
| Qwen | 178 | 56 | ~1814 | **0.998** | ~4.2× |
| GPT-5.1 | 39 | 49 | ~1558 | **1.000** | ~4.1× |
| GPT-5.5 | 210 | 56 | ~2156 | **1.000** | ~4.5× |
| Sonnet* | 174 | 54 | ~2415 | **1.000** | ~4.4× |
| Sol (5.6) | 32 | 47 | ~1896 | **1.000** | ~4.3× |
| Opus | 10 | 49 | ~2774 | **0.998** | ~4.7× |

\*Includes Haiku-labeled `pixel[...]` runs that share `PixelBrowserAgent`;
true `pixel[claude-sonnet-4-6]` long eps show the same linear ramp (e.g. s0
~5.7k → s29 ~80k → s49 ~140k).

### Named checkpoints (illustrative)

| Family | Example | s0 | ~s9 | ~s29 | late |
|--------|---------|---:|----:|-----:|-----:|
| GPT-5.5 | M141 seed2 @120 (`cascade_all`) | 4.7k | 22k | 63k | **253k @119** |
| GPT-5.1 | M32 seed1 @74 | 4.5k | 17k | 46k | **111k @73** |
| Sol | M213 seed0 @50 | 4.6k | 21k | 58k | **95k @49** |
| Opus | M148 seed0 @50 | 6.6k | 28k | 84k | **151k @49** |
| Sonnet-4.6 | M232 seed2 @50 | 5.7k | — | 83k | **142k @49** |
| Qwen | M41 seed2 @93 | 5.3k | 18k | 29k | **66k @92** (smaller `c`, still linear) |

Gemini measured growth (~1.8k/step to ~112k @60) is documented in the Gemini
step-60 audit; no Gemini trajs in the local cascade tree (pilot results JSON
only), but code path is the shared openai_pixel loop.

### Theoretical inflation vs truncated history

For full resend vs keep-last-**K** frames, frame-counts per episode are
`N(N+1)/2` vs `K(K+1)/2 + K(N−K)` (`N>K`). For typical long `N≈50`:

| Policy | Relative input volume vs full history |
|--------|----------------------------------------|
| Keep last 1 | ~**4%** of full (≈ **96%** of billed input is “extra”) |
| Keep last 5 | ~**19%** of full (≈ **81%** extra) |
| Keep last 10 | ~**36%** of full (≈ **64%** extra) |

Empirical `sum(tokens_in) / (N · tokens_in[N−1]/N)` on long eps is
~**23–30×** ≈ `(N+1)/2`, matching full triangular resend (not a flat context).

---

## Rough historical cost impact

Rates from `eval/cost_tracker.py` ($/MTok in|out): qwen 0.20|0.88,
gpt-5.1 1.25|10, gpt-5.5 / sol 5|30, sonnet 3|15, opus 5|25, gemini 2|12.

**Order of magnitude (sonnet-completions worktree traj root, all eps with
`tokens_in`):**

| Tier | eps | sum `tokens_in` | rough $ (in+out) | long40+ share of in | ~extra $ on long40+ if last-1 only* |
|------|----:|----------------:|-----------------:|--------------------:|-----------------------------------:|
| gpt-5.5 | 584 | 580M | ~**$3080** | 401M | ~**$1900** |
| sonnet | 701 | 629M | ~**$1990** | 399M | ~**$1150** |
| qwen | 928 | 564M | ~$116 | 235M | ~$45 |
| gpt-5.1 | 920 | 226M | ~$289 | 54M | ~$65 |
| sol | 171 | 83M | ~$438 | 33M | ~$160 |
| opus | 142 | 69M | ~$370 | 18M | ~$85 |

\*Counterfactual: bill only one frame per turn (`sum ≈ c·N` instead of
`c·N(N+1)/2`). Short episodes have little triangular waste; **long thrash
dominates**. Keep-last-5 would still leave ~80% of long-episode input as
re-billing overhead.

**cascade_all (main repo slice):** gpt-5.5 long40+ alone ~29M input tokens
(~$144 in-cost); ~97% of that is triangular vs last-1.

**Gemini pilots** (separate): thrash @120 averaged ~13M tokens_in / ~$27/ep
at Gemini rates — same `N²` law; higher because budget/step cap allow larger
`N` than Qwen’s 60k guard.

**Takeaway:** Historical cascade / prepub / cross-model SoM spend is inflated
by **full screenshot history resend on every family**, not a Gemini quirk.
Gemini is the loudest instance because `LLM_CONTEXT_BUDGET=900k` + 120 steps
lets `N` grow furthest; Qwen’s lower budget **cuts episodes earlier** but
does not truncate the message list while the episode is alive.

---

## Implications (analysis only; no code changes here)

1. Any fix (keep-last-K, sliding window, text-only older turns) should land in
   **shared** `OpenAIPixelAgent` + `PixelBrowserAgent` (and coord twins), not
   only Gemini.
2. Per-tier `LLM_CONTEXT_BUDGET` is a **cost/length brake**, not a history
   compressor — it changes how far triangular growth runs.
3. Cost projections that assume constant tokens/step understate thrash by
   ~`(N+1)/2` for full-resend SoM.

---

## Sources

- Code: `agents/openai_pixel_agent.py`, `agents/gemini_pixel_agent.py`,
  `agents/qwen_agent.py`, `agents/pixel_agent.py`, `eval/cascade_v2.py`
  `CONTEXT_BUDGET`, `deploy/gcp_gemini_screen` (`LLM_CONTEXT_BUDGET=900000`)
- Data: traj trees under main `trajectories/` +
  `../ecommerce-browser-gym-sonnet-completions/trajectories/`; Gemini pilot
  totals from prior audit / `deploy/gcp_gemini_screen/out_pilot_*`
- Sampling: `.venv/bin/python` JSON load of episode files; no new model runs
