"""Normalize all 45 missing-screenshot tasks into ONE folder structure.

Target layout (documented in each task's SOURCE.md):

    screenshots/{Mxx__slug}/
      SOURCE.md
      seed_state/
        seed{N}_initial.png            live gym capture 2026-07-24 (post infra fix)
        seed{N}_initial.live.json      world dump paired with that PNG
        seed{N}_initial.json           factory world JSON (seed_snapshots)
        seed{N}_final.json             factory world JSON (seed_snapshots)
        seed{N}_final_oracle.png       last frame of an oracle episode (state
                                       after CORRECT completion), when available
        static_start.png               static BrowerGym GitHub Pages capture
      oracle/seed{N}__{hash}/step_XXX.png
      models/{model}/seed{N}__{hash}/  recovered + historical filmstrips
        step_XXX.png
        seed_initial.png/.json, seed_final.png/.json   (replayed episodes)
        REPLAY_RECOVERY.json                            (replayed episodes)

Files are HARDLINKED from their source locations (copy fallback), so the
historical `screenshots/` buckets keep working and no bytes are duplicated.
No trajectory or ledger file is modified.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
STATIC_SEEDS = ROOT / "docs/history/audits/artifacts/static_seeds_2026-07-24"

TASK_IDS = [
    'M40', 'M41', 'M47', 'M51', 'M57', 'M68', 'M72', 'M73', 'M74', 'M76',
    'M77', 'M78', 'M79', 'M81', 'M82', 'M83', 'M84', 'M86', 'M87', 'M90',
    'M91', 'M92', 'M93', 'M94', 'M95', 'M96', 'M97', 'M98', 'M99', 'M100',
    'M101', 'M102', 'M104', 'M148', 'M164', 'M200', 'M207', 'M210', 'M212',
    'M214', 'M217', 'M219', 'M220', 'M224', 'M227',
]
REPLAY_16 = {'M77', 'M78', 'M79', 'M84', 'M87', 'M90', 'M91', 'M93', 'M98',
             'M99', 'M100', 'M101', 'M102', 'M104', 'M207', 'M210'}


def slug_map() -> dict[str, str]:
    out = {}
    for d in os.listdir(ROOT / 'seed_snapshots'):
        if '__' in d:
            out[d.split('__')[0]] = d
    return out


def link(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def model_of(agent_name: str) -> str:
    m = re.search(r'\[(.+)\]', agent_name or '')
    return m.group(1) if m else (agent_name or 'unknown')


def main() -> None:
    slugs = slug_map()
    mid_pat = re.compile(r'^(M\d+)_')

    # 1. index every trajectory of the 45 tasks: hash -> episode meta
    episodes: dict[str, dict] = {}
    for p in glob.glob(str(ROOT / 'trajectories/**/*.jsonl'), recursive=True):
        base = os.path.basename(p)
        m = mid_pat.match(base)
        if not m or m.group(1) not in TASK_IDS:
            continue
        try:
            obj = json.loads(Path(p).read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(obj, dict) or 'episode_id' not in obj:
            continue
        steps = obj.get('steps') or []
        shots_dir = None
        if steps and steps[0].get('screenshot_path'):
            shots_dir = str(Path(
                steps[0]['screenshot_path'].replace('\\', '/')).parent)
        episodes[obj['episode_id']] = {
            'traj': os.path.relpath(p, ROOT),
            'mid': m.group(1),
            'task_id': obj.get('task_id'),
            'seed': obj.get('seed'),
            'agent_name': obj.get('agent_name'),
            'n_steps': len(steps),
            'shots_dir': shots_dir,
            'hist_success': (obj.get('verifier_result') or {}).get('success'),
        }

    # 2. index every on-disk screenshot episode dir for the 45 tasks
    hash_pat = re.compile(r'__([0-9a-f]{8})$')
    per_task_rows: dict[str, list[dict]] = defaultdict(list)
    seen_dirs: set[str] = set()
    SKIP_BUCKETS = {'_demo_sonnet', 'prepublication_m37_20260715',
                    'prepublication_oracles_20260715', 'qwen'}
    for bucket in sorted(os.listdir(ROOT / 'screenshots')):
        broot = ROOT / 'screenshots' / bucket
        if not broot.is_dir():
            continue
        # Skip already-normalized per-task dirs and non-bucket folders
        if '__' in bucket and bucket.startswith('M'):
            continue
        if bucket in SKIP_BUCKETS:
            continue
        for d in sorted(broot.iterdir()):
            if not d.is_dir():
                continue
            m = mid_pat.match(d.name)
            if not m or m.group(1) not in TASK_IDS:
                continue
            hm = hash_pat.search(d.name)
            ep = episodes.get(hm.group(1)) if hm else None
            pngs = sorted(d.glob('*.png'))
            if not pngs:
                continue
            mid = m.group(1)
            seed = ep['seed'] if ep else (
                int(d.name.split('__')[-2]) if d.name.count('__') >= 2 else '?')
            agent = ep['agent_name'] if ep else None
            replayed = (d / 'REPLAY_RECOVERY.json').exists()
            if agent == 'oracle' or (agent is None and bucket == 'oracle'):
                group, sub = 'oracle', f"seed{seed}__{hm.group(1) if hm else d.name[-8:]}"
            elif agent is None:
                group, sub = 'models/_unattributed', f"{bucket}__{d.name}"
            else:
                group = f"models/{model_of(agent)}"
                sub = f"seed{seed}__{hm.group(1)}"
            dst = OUT / slugs[mid] / group / sub
            for f in sorted(d.iterdir()):
                if f.is_file():
                    link(f, dst / f.name)
            seen_dirs.add(str(d.relative_to(ROOT)))
            per_task_rows[mid].append({
                'dest': str(dst.relative_to(OUT / slugs[mid])),
                'source': str(d.relative_to(ROOT)),
                'bucket': bucket,
                'agent': agent or f'(unattributed: {bucket})',
                'seed': seed,
                'n_frames': len(pngs),
                'n_steps_traj': ep['n_steps'] if ep else None,
                'traj': ep['traj'] if ep else None,
                'hist_success': ep['hist_success'] if ep else None,
                'provenance': ('replay-recovered 2026-07-24 (visual only; '
                               'historical verdict is ground truth)')
                              if replayed else 'historical on-disk',
            })

    # 3. seed_state: factory JSONs, static start page, oracle-final frames
    for mid in TASK_IDS:
        sdir = OUT / slugs[mid] / 'seed_state'
        sdir.mkdir(parents=True, exist_ok=True)
        snap_src = ROOT / 'seed_snapshots' / slugs[mid]
        for seed in (0, 1, 2):
            for kind in ('initial', 'final'):
                f = snap_src / f'seed{seed}_{kind}.json'
                if f.exists():
                    link(f, sdir / f.name)
        # static BrowerGym start page (one per task)
        for f in STATIC_SEEDS.glob(f'{mid}__*.png'):
            link(f, sdir / 'static_start.png')
        # oracle final state = last frame of an oracle episode per seed
        got: dict[int, tuple[int, Path]] = {}
        for row in per_task_rows[mid]:
            if not row['dest'].startswith('oracle/'):
                continue
            src_dir = ROOT / row['source']
            frames = sorted(src_dir.glob('step_*.png'))
            if not frames:
                continue
            try:
                seed = int(row['seed'])
            except Exception:
                continue
            # prefer the longest filmstrip for that seed
            if seed not in got or len(frames) > got[seed][0]:
                got[seed] = (len(frames), frames[-1])
        for seed, (_, frame) in got.items():
            link(frame, sdir / f'seed{seed}_final_oracle.png')

    # 4. SOURCE.md per task
    for mid in TASK_IDS:
        rows = sorted(per_task_rows[mid],
                      key=lambda r: (r['dest'],))
        task_dir = OUT / slugs[mid]
        lines = [
            f"# {slugs[mid].replace('__', '/', 1)} — visual evidence sources",
            "",
            "Normalized 2026-07-24 by `scripts/normalize_task_visuals.py`. "
            "Files are hardlinks into the historical `screenshots/` buckets "
            "(originals untouched). **Historical trajectory dispositions are "
            "ground truth** — nothing here re-judges an episode.",
            "",
            "## seed_state/",
            "",
            "| file | origin |",
            "|---|---|",
            "| `seed{N}_initial.png` + `.live.json` | live gym capture "
            "2026-07-24 (post infra fix), `scripts/capture_seed_initials.py`, "
            "$0 API |",
            "| `seed{N}_initial.json` / `seed{N}_final.json` | factory world "
            f"dumps from `seed_snapshots/{slugs[mid]}/` |",
            "| `seed{N}_final_oracle.png` | last frame of the longest oracle "
            "filmstrip for that seed (state after correct completion) |",
            "| `static_start.png` | static BrowerGym GitHub Pages capture, "
            "`docs/history/audits/artifacts/static_seeds_2026-07-24/` |",
            "",
            "## Filmstrips",
            "",
            "| dest | source | agent | seed | frames | steps | historical "
            "success | provenance |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| `{r['dest']}` | `{r['source']}` | {r['agent']} | "
                f"{r['seed']} | {r['n_frames']} | {r['n_steps_traj'] or '-'} "
                f"| {r['hist_success']} | {r['provenance']} |")
        if mid in REPLAY_16:
            lines += [
                "",
                "> This task is one of the 16 whose model filmstrips were "
                "lost; its `models/` dirs were regenerated by mechanical "
                "replay of the recorded action sequences "
                "(`scripts/replay_visual_recovery.py`, no model, $0 API). "
                "See each episode's `REPLAY_RECOVERY.json` for per-step "
                "fidelity (URL match ratio) and the explicitly "
                "non-authoritative replay verifier output.",
            ]
        (task_dir / 'SOURCE.md').write_text('\n'.join(lines) + '\n',
                                            encoding='utf-8')

    # 5. summary
    n_rows = sum(len(v) for v in per_task_rows.values())
    print(f"tasks: {len(TASK_IDS)}; filmstrip dirs linked: {n_rows}")
    missing = [t for t in TASK_IDS if not per_task_rows[t]]
    print("tasks with zero filmstrips:", missing or "none")


if __name__ == '__main__':
    main()
