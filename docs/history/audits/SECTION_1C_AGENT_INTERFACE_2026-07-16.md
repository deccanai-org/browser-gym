# Section 1C agent-interface validity — 2026-07-16

Covers protocol §1C: screenshot resolution parity, popup-tab tracking,
native-`<select>` construct-validity, **prompt byte-identity**,
**action-space equivalence**, and **broad SoM completeness**. Prior Xbay
quantity work remains in
[SECTION_1C_MARKETPLACE_QUANTITY_INPUT_2026-07-15.md](SECTION_1C_MARKETPLACE_QUANTITY_INPUT_2026-07-15.md).

Focused tests: `tests/test_section1c_agent_interface.py` (**8 passed** after
2026-07-16 advance). Artifacts: `trajectories/prepublication_section1c_20260716/`.

**Paid models:** none this pass for §1C harness items (M43 popup paid rescreen
documented separately).

---

## 1. Screenshot resolution parity — PARTIAL (capture pinned; detail asymmetric)

**Advance 2026-07-16 (same day):** harness now **pins and records** capture
geometry + provider encoding profiles.

**Pinned capture (`harness/runner.py`):**

| Pin | Value |
|---|---|
| viewport | **1280×800** (`PINNED_VIEWPORT`) |
| device_scale_factor | **1.0** (`PINNED_DEVICE_SCALE_FACTOR`) |
| screenshot | PNG, `full_page=False` |

**Recorded metadata:**

- `Trajectory.image_settings` — viewport/DPR + provider profile (`detail` /
  format / API note) via `image_settings_for_agent`
- `StepRecord.screenshot_width` / `screenshot_height` / `device_pixel_ratio`
- `eval/cascade_v2` writes `screenshot_pinning.json` per cascade tree

**Provider encoding (documented + recorded):**

| Runner | Image detail pin |
|---|---|
| OpenAI pixel / coord | `detail="high"` |
| Qwen pixel | **inherits** OpenAIPixelAgent `detail="high"` |
| Anthropic pixel / coord | PNG base64, **no** detail field (API has no knob) |

**Still open:** cross-provider **detail equivalence** (Anthropic cannot match
OpenAI/Qwen `detail="high"`). Do not claim pixel observations are
provider-identical on the detail axis.

Evidence:

- `screenshot_resolution.json`
- `provider_image_encoding_inventory.json`
- `screenshot_cascade_pinning.json`

**Disposition:** capture/metadata pins **advanced**; keep P0 **open** only for
cross-provider detail equivalence.

---

## 2. Popup-tab tracking — CLOSED (post-fix verified)

**Bug / fix:** as previously documented — `BrowserCtx` now tracks
`window.open` popups into `pages` / tab strip.

**Post-fix verification:** harness unit **and** paid M43 cascade rescreen
(2026-07-16). Evidence:
[SECTION_1C_POPUP_TRACKING_POSTFIX_2026-07-16.md](SECTION_1C_POPUP_TRACKING_POSTFIX_2026-07-16.md),
[M43_POPUP_RESCREEN_2026-07-16.md](M43_POPUP_RESCREEN_2026-07-16.md),
`popup_tracking.json`, and
`trajectories/prepublication_m43_popup_rescreen_20260716/cascade/`.

**Other sellables:** only **M43** has a gold-path / success dependency on
tracking content. M211/M213/M217/M220/M224 may see the View-tracking control
on order detail but do not require the popup. **None besides M43** needed a
popup-fix rescreen for success construct.

**M43 paid rescreen:** COMPLETE — Qwen 2/3, GPT-5.1 2/3, GPT-5.5 1/3 (stop);
retained as gpt-5.1-only footnote. Pre-fix panels superseded for publication.

---

## 3. Native `<select>` construct-validity — PARTIAL (32/32 table done)

**Inventory:** **32/85** sellables (`native_select_inventory.json`).

**Motor-vs-reasoning:** **32/32** audited —
[SECTION_1C_NATIVE_SELECT_MOTOR_VS_REASONING_2026-07-16.md](SECTION_1C_NATIVE_SELECT_MOTOR_VS_REASONING_2026-07-16.md)
+ `native_select_motor_vs_reasoning.json`.

| Result | Count |
|---|---|
| Primary = reasoning | 32 |
| Primary = motor | 0 |
| Reclassified UI-wrapper | 0 |

Every inventoried sellable has corpus break episodes with forbidden milestones
fired (trap completed). DOM `select()` vs pixel ArrowDown asymmetry remains a
**disclosure** for cross-modality claims; incompletes may still confound.
No mass removal. Keep protocol item **open** for disclosure / incompletes.

---

## 4. Task-prompt byte-identity — CLOSED (within cascade runners)

`eval/run.py` passes `reset["task_brief"]` unchanged into every agent kind.
Reset replay (same seed) + banner unescape + embeddings across DOM / pixel /
coord / qwen wrappers agree **byte-for-byte** on the brief
(`prompt_byte_identity.json`). Modality *wrap* text differs (`TASK:` vs
`## TASK`); brief bytes do not.

---

## 5. Action-space equivalence — PARTIAL (within-modality closed)

Within a modality, Anthropic / OpenAI / Qwen share the same tool **names**
(`action_space_equivalence.json`). Cross-modality is intentionally unequal:

- DOM: `navigate/click/fill/select/check/submit/...` (no `wait` in TOOLS list)
- Pixel SoM: `click/type_text/key/scroll/.../wait` (no `select`)
- Coord: `click_at/type_at/key/.../wait` (no `select`)

Formal disclosure: `action_space_cross_modality_disclosure.json` (capability
matrix; 32 sellables affected by native-select asymmetry).

Keep P0 **open** for any claim that pixel and DOM action spaces are
equivalent; within-modality cascade comparisons are schema-equivalent.
Cross-modality non-equivalence is architectural, not an incomplete audit.

---

## 6. SoM completeness (broad) — PARTIAL (surface inventory)

**Scoped closed (prior):** Xbay quantity construct
(`trajectories/prepublication_section1c_20260715/marketplace_quantity.json`).

**Broad advance 2026-07-16:** live `extract_marks` inventory on **7** dense
surfaces (shop home/product/cart, mail, calendar, orders, market product).
Omission taxonomy documented (`som_omission_taxonomy.json` /
`som_completeness_inventory.json`):

| Omission class | Notes |
|---|---|
| hidden / opacity | Intentional (matches quantity finding) |
| min dimension 8px | Filter |
| offscreen | Viewport cull |
| non-interactable role | Outside `_INTERACTABLE_ROLES` |
| IoU dedupe / max 80 | Structural silent-drop risk on dense pages |

No sampled surface hit the 80-mark hard cap; eligible visible == marks on all
7. Universal “no interactive element silently omitted” remains unprovable
given cap-80 + IoU design. Keep **P0 open**.

---

## Protocol checkbox summary

| Item | Status |
|---|---|
| Screenshot resolution identical across models | **PARTIAL** — capture 1280×800 + DPR=1 pinned + traj/cascade metadata; Anthropic detail knob absent |
| SoM completeness (broad) | **OPEN / PARTIAL** — 7-surface inventory + taxonomy; quantity case scoped closed |
| Task prompts byte-identical across models | **CLOSED** — `prompt_byte_identity.json` |
| Action spaces equivalent across models | **PARTIAL** — within-modality yes; cross-modality disclosed non-equivalent |
| Native `<select>` blind spot | **PARTIAL** — 32/32 motor-vs-reasoning table; no mass reclass |
| Popup tabs tracked | **CLOSED** — post-fix harness + M43 paid rescreen |

### Still named open (architectural / disclosure — not unfinished audits)

As of 2026-07-16 advance: remaining §1C P0 opens are **disclosed structural
limits**, not missing inventory work. Do not keep grinding harness audits
expecting a universal close without API/design changes.

- Cross-provider image **detail** equivalence (Anthropic has no knob; capture geometry is pinned)
- Broad SoM completeness (universal no-silent-omit) — taxonomy + 7-surface
  inventory documented; cap-80/IoU structural risk remains; no further
  harness “prove universal completeness” claim without design change
- Cross-modality action-space equivalence (disclose; do not claim equivalent) —
  matrix in `action_space_cross_modality_disclosure.json`; mirrored in
  `PROJECT_INFO.md` §9
- Native-select incompletes / disclosure (32/32 table done; item not fully
  closed) — disclosure sentence in
  [native-select audit](SECTION_1C_NATIVE_SELECT_MOTOR_VS_REASONING_2026-07-16.md)
