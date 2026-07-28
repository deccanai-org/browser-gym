# Section 1C — popup-tracking post-fix validation — 2026-07-16

Sibling to
[SECTION_1C_AGENT_INTERFACE_2026-07-16.md](SECTION_1C_AGENT_INTERFACE_2026-07-16.md).

## Was M43 verified **after** the `BrowserCtx` fix?

**Yes — harness/unit AND paid cascade rescreen.**

| Artifact | Role | Timestamp / status |
|---|---|---|
| `harness/runner.py` (`_install_popup_tracking` / `_sync_context_pages`) | Fix | 2026-07-16 |
| `tests/test_section1c_agent_interface.py::test_tracking_popup_enters_tab_strip` | Post-fix unit | PASS |
| `trajectories/prepublication_section1c_20260716/popup_tracking.json` | Unit evidence | post_fix_verified |
| Fresh cascade k=3 under fixed harness | Paid rescreen | **COMPLETE 2026-07-16** — Qwen 2/3, GPT-5.1 2/3, GPT-5.5 1/3 stop |

Paid rescreen evidence:
[M43 popup rescreen audit](M43_POPUP_RESCREEN_2026-07-16.md) and
`trajectories/prepublication_m43_popup_rescreen_20260716/cascade/`.

## Other sellables that open popups / new windows?

Repo-wide UI search: **only**
`ui/pages/account_order_detail.html` uses `window.open` (View tracking).
No other `target=_blank` / `window.open` in `ui/`.

| Sellable | Gold path uses `/track` or popup? | Order-detail exposure? |
|---|---|---|
| **M43/stale_delivery_date** | Yes — needs live tracking ETA | Yes — **only sellable whose success depends on tracking content** |
| M211, M213, M217, M220, M224 | No gold-path tracking/popup | May visit order detail (link visible); **not** required for success |
| All other sellables (N=85) | No | No |

**Verdict:** **none besides M43** have a gold-path / success dependency on the
popup. No mass re-screen indicated for the other five at harness level.

## Membership / hold

M43 **retained** (gpt-5.1-only footnote) after clean post-fix reproduction.
No hold. Pre-fix model panels superseded for publication claims.
