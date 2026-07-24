"""Consolidate artifacts/task_visuals/ into screenshots/{Mxx__slug}/.

Moves the canonical per-task visual layout from
`artifacts/task_visuals/{Mxx__slug}/` to `screenshots/{Mxx__slug}/` using
hardlinks (same filesystem, no byte duplication). Historical bucket dirs
(`screenshots/{oracle,pixel,openai_pixel,harvest}/`) are left intact so
trajectory `screenshot_path` values keep resolving.

After linking:
  - SOURCE.md text is rewritten to name screenshots/ as the home
  - artifacts/task_visuals/ is replaced with a DEPRECATED.md pointer plus
    per-task symlinks back into screenshots/ (keeps forensic doc paths alive)

Does NOT touch trajectories/sellable_breakers_v2.csv or any trajectory JSONL.

Usage:
    .venv/bin/python scripts/consolidate_task_visuals_to_screenshots.py
    .venv/bin/python scripts/consolidate_task_visuals_to_screenshots.py --retire
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "artifacts" / "task_visuals"
DST_ROOT = ROOT / "screenshots"
SELLABLE = ROOT / "trajectories" / "sellable_breakers_v2.csv"

EXPECTED_SHA256 = (
    "c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30"
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def link(src: Path, dst: Path) -> str:
    """Hardlink src -> dst. Returns 'linked' | 'exists' | 'copied'."""
    if dst.exists():
        # already same inode?
        try:
            if dst.stat().st_ino == src.stat().st_ino:
                return "exists"
        except OSError:
            pass
        return "exists"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
        return "linked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


def rewrite_source_md(text: str) -> str:
    text = text.replace(
        "artifacts/task_visuals/",
        "screenshots/",
    )
    text = text.replace(
        "Files are hardlinks into the historical `screenshots/` buckets "
        "(originals untouched).",
        "Canonical home is `screenshots/{Mxx__slug}/`. Files are hardlinks "
        "into the historical `screenshots/{oracle,pixel,openai_pixel,harvest}/` "
        "buckets (originals untouched).",
    )
    # note consolidation if not already present
    if "consolidate_task_visuals_to_screenshots.py" not in text:
        text = text.replace(
            "Normalized 2026-07-24 by `scripts/normalize_task_visuals.py`.",
            "Normalized 2026-07-24 by `scripts/normalize_task_visuals.py`; "
            "consolidated into `screenshots/` 2026-07-24 by "
            "`scripts/consolidate_task_visuals_to_screenshots.py`.",
        )
    return text


def count_tree(root: Path) -> tuple[int, int, int]:
    """Returns (n_files, n_filmstrip_dirs, n_task_dirs)."""
    if not root.exists():
        return 0, 0, 0
    n_files = 0
    n_film = 0
    tasks = [d for d in root.iterdir() if d.is_dir() and "__" in d.name
             and d.name.startswith("M")]
    for t in tasks:
        for p in t.rglob("*"):
            if p.is_file():
                n_files += 1
        for d in t.rglob("*"):
            if d.is_dir() and any(d.glob("step_*.png")):
                n_film += 1
    return n_files, n_film, len(tasks)


def consolidate() -> dict:
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}")

    before = count_tree(SRC)
    stats = {"linked": 0, "exists": 0, "copied": 0, "tasks": 0, "md": 0}

    task_dirs = sorted(
        d for d in SRC.iterdir()
        if d.is_dir() and d.name.startswith("M") and "__" in d.name
    )
    for tdir in task_dirs:
        stats["tasks"] += 1
        dest_task = DST_ROOT / tdir.name
        for src_file in tdir.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(tdir)
            dst_file = dest_task / rel
            if src_file.name == "SOURCE.md":
                # write rewritten content (new inode; fine — markdown only)
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                new_text = rewrite_source_md(
                    src_file.read_text(encoding="utf-8"))
                dst_file.write_text(new_text, encoding="utf-8")
                stats["md"] += 1
                continue
            result = link(src_file, dst_file)
            stats[result] += 1

    after = count_tree(DST_ROOT)
    return {
        "src_before": before,
        "dst_after": after,
        "stats": stats,
    }


def retire() -> None:
    """Replace artifacts/task_visuals contents with pointer + symlinks."""
    if not SRC.exists():
        return
    # Remove real trees (hardlinked data remains under screenshots/)
    for child in list(SRC.iterdir()):
        if child.is_symlink():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    (SRC / "DEPRECATED.md").write_text(
        "# Deprecated — moved to `screenshots/{Mxx__slug}/`\n\n"
        "Per-task visual evidence for the 45 missing-screenshot tasks was "
        "consolidated into `screenshots/{Mxx__slug}/` on 2026-07-24 "
        "(see `scripts/consolidate_task_visuals_to_screenshots.py` and "
        "`docs/history/audits/SCREENSHOT_CONSOLIDATE_45_TO_SCREENSHOTS_"
        "2026-07-24.md`).\n\n"
        "Each `{Mxx__slug}` entry here is a **symlink** into "
        "`../../screenshots/{Mxx__slug}` so older doc paths keep resolving.\n"
        "Do not write new captures here — use "
        "`scripts/capture_seed_initials.py` / "
        "`scripts/normalize_task_visuals.py` (both now target "
        "`screenshots/`).\n",
        encoding="utf-8",
    )

    for d in sorted(DST_ROOT.iterdir()):
        if d.is_dir() and d.name.startswith("M") and "__" in d.name:
            link_path = SRC / d.name
            if link_path.exists() or link_path.is_symlink():
                continue
            os.symlink(os.path.relpath(d, SRC), link_path)


def verify_structure() -> list[str]:
    problems = []
    tasks = sorted(
        d for d in DST_ROOT.iterdir()
        if d.is_dir() and d.name.startswith("M") and "__" in d.name
    )
    if len(tasks) != 45:
        problems.append(f"expected 45 task dirs, found {len(tasks)}")
    for t in tasks:
        if not (t / "SOURCE.md").exists():
            problems.append(f"{t.name}: missing SOURCE.md")
        ss = t / "seed_state"
        if not ss.is_dir():
            problems.append(f"{t.name}: missing seed_state/")
            continue
        for seed in (0, 1, 2):
            for name in (f"seed{seed}_initial.png",
                         f"seed{seed}_initial.live.json",
                         f"seed{seed}_initial.json",
                         f"seed{seed}_final.json",
                         f"seed{seed}_final_oracle.png"):
                if not (ss / name).exists():
                    problems.append(f"{t.name}: missing seed_state/{name}")
        if not (ss / "static_start.png").exists():
            problems.append(f"{t.name}: missing seed_state/static_start.png")
        if not (t / "oracle").is_dir() or not any((t / "oracle").iterdir()):
            problems.append(f"{t.name}: missing/empty oracle/")
        # models optional for sparse cells but expect at least one for most
        if not (t / "models").is_dir():
            problems.append(f"{t.name}: missing models/")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--retire", action="store_true",
        help="After consolidate, replace artifacts/task_visuals with "
             "DEPRECATED.md + per-task symlinks")
    ap.add_argument(
        "--skip-consolidate", action="store_true",
        help="Only run retire / verify (assume screenshots/ already built)")
    args = ap.parse_args()

    sellable_sha = sha256_file(SELLABLE)
    if sellable_sha != EXPECTED_SHA256:
        print(f"WARN: sellable CSV sha mismatch: {sellable_sha}",
              file=sys.stderr)

    if not args.skip_consolidate:
        result = consolidate()
        print("consolidate:", result["stats"])
        print("src_before files/film/tasks:", result["src_before"])
        print("dst_after  files/film/tasks:", result["dst_after"])
        sf, sfilm, st = result["src_before"]
        df, dfilm, dt = result["dst_after"]
        # dst film/files should be >= src (SOURCE.md rewritten so file count
        # for binary assets should match; SOURCE.md is new write)
        if st != 45 or dt != 45:
            raise SystemExit(f"task count mismatch src={st} dst={dt}")
        if dfilm != sfilm:
            raise SystemExit(
                f"filmstrip dir count mismatch src={sfilm} dst={dfilm}")
        # file count: SOURCE.md rewritten (not hardlinked) so expect
        # dst files == src files (same count of files)
        if df != sf:
            raise SystemExit(
                f"file count mismatch src={sf} dst={df}")

    if args.retire:
        retire()
        print("retired artifacts/task_visuals/ -> DEPRECATED.md + symlinks")

    problems = verify_structure()
    if problems:
        print(f"VERIFY PROBLEMS ({len(problems)}):")
        for p in problems[:40]:
            print(" ", p)
        if len(problems) > 40:
            print(f"  ... +{len(problems) - 40} more")
        raise SystemExit(1)

    sellable_sha_after = sha256_file(SELLABLE)
    print(f"sellable sha before/after: {sellable_sha} / {sellable_sha_after}")
    if sellable_sha_after != EXPECTED_SHA256:
        raise SystemExit("sellable CSV changed — abort")
    print("OK: 45 tasks under screenshots/{Mxx__slug}/, structure verified")


if __name__ == "__main__":
    main()
