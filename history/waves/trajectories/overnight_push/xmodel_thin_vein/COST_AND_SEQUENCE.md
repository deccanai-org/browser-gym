# M342–M350 thin-vein cost-root & sequence

**cost-root** = this directory (`trajectories/overnight_push/xmodel_thin_vein/`).

## ⚠️ DISCARDED / OUT-OF-SCOPE (2026-07-14) — Sol/Opus thread CLOSED

The M342–M350 **Sol + Opus** screen under this cost-root (stamp `20260713_182947`) is
**DISCARDED**. Those results do **NOT** count toward:

- confirmed breakers
- sellable merge
- forensic tallies
- any working-set / vein distribution going forward

Trajectory folders (`sol/`, `opus/`) are **retained on disk** for audit only; treat them as
out-of-scope artifacts. Do **not** relaunch Sol/Opus for this wave.

**Watchdog / respawner:** **DISARMED** 2026-07-14 (respawner pid 53984 + watchdog pid 53985
stopped; xmodel18 watchdog tree also stood down). Sol/Opus worker pids were already dead.

**Canonical path for M342–M350 going forward:** the real confirmed-breaker cascade
(`Qwen → gpt-5.1 → gpt-5.5 → Sonnet`, escalate ≥2/3, K=3) under
`trajectories/overnight_push/thin_vein_cascade/` (oracle already PASSED at
`trajectories/thin_vein_oracle/` — skipped).

---

**Historical (discarded) screen note:** cap was **$550**; Sol $50.75 / Opus $1.47; ports
:8140 / :8142. Tasks only from `tasks9.txt` (M342–M350). Never shared cost-root with
`xmodel18` ($900).

## Sequencing (locked)

1. ~~Finish Sol/Opus `xmodel18`~~ **DONE**
2. ~~Finish forensic on prior Sol/Opus breaks~~ **DONE** (43 confirmed / 2 held)
3. ~~Launch M342–M350 Sol+Opus screen~~ **DONE then DISCARDED** (do not count)
4. **Run M342–M350 on real cascade_v2** → see `../thin_vein_cascade/`

Task list: `tasks9.txt`.
