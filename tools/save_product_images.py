"""Download licensed Adobe Stock images, resize, and place them for the mocks.

Input: a JSON file mapping product_id -> a presigned download URL (the URL
`asset_license_and_download_stock` returns). Produced by the orchestrator after
licensing the curated free-collection assets.

Canonical home for the binaries is tools/product_assets/products/<id>.jpg (in
the repo, version-controlled). build_hub_mocks.sh copies that tree into each
mock's public/assets/ at build time, so the images ship in every deployment.
For an immediate local preview this also copies into the running hubdev mocks.

Writes tools/product_images.json (the manifest the projection reads to decide
local-image vs picsum fallback).

  python -m tools.save_product_images urls.json
  python -m tools.save_product_images urls.json --edge 800
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
CANON = REPO / "tools" / "product_assets" / "products"
MANIFEST = REPO / "tools" / "product_images.json"

# The running local working tree (patched, what vite preview serves). Optional —
# only used so a re-seed shows the images without a full rebuild.
HUBDEV = pathlib.Path(
    "/private/tmp/claude-501/-Users-dhiren-Deccan-AI-E-Commerce-Broswer-Gym/"
    "a606619c-c162-479f-8fd5-31923f720770/scratchpad/hubdev")
LIVE_MOCKS = ("amazon_mock", "ebay_mock")


def _resize(src: pathlib.Path, dst: pathlib.Path, edge: int) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # sips ships on macOS; -Z fits the longest edge, preserving aspect ratio.
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-Z", str(edge),
                        str(src), "--out", str(dst)],
                       capture_output=True, text=True)
    return r.returncode == 0 and dst.exists()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls_json", help="JSON: {product_id: presigned_url}")
    ap.add_argument("--edge", type=int, default=800, help="longest-edge px (default 800)")
    args = ap.parse_args(argv)

    urls: dict[str, str] = json.loads(pathlib.Path(args.urls_json).read_text())
    CANON.mkdir(parents=True, exist_ok=True)

    done, failed = [], []
    tmp = pathlib.Path(tempfile.mkdtemp())
    for pid, url in urls.items():
        raw = tmp / f"{pid}.raw"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                raw.write_bytes(r.read())
        except Exception as e:
            print(f"  !! {pid}: download failed — {e}")
            failed.append(pid)
            continue
        canon = CANON / f"{pid}.jpg"
        if not _resize(raw, canon, args.edge):
            print(f"  !! {pid}: resize failed")
            failed.append(pid)
            continue
        # mirror into the running mocks for an instant local preview
        for m in LIVE_MOCKS:
            d = HUBDEV / "websites" / m / "public" / "assets" / "products" / f"{pid}.jpg"
            if (HUBDEV / "websites" / m).exists():
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(canon.read_bytes())
        kb = canon.stat().st_size / 1024
        print(f"  ok {pid:24} {kb:6.0f} KB")
        done.append(pid)

    # manifest = union of whatever already existed + the new ones
    have = set(json.loads(MANIFEST.read_text())) if MANIFEST.exists() else set()
    have.update(done)
    MANIFEST.write_text(json.dumps(sorted(have), indent=0))
    print(f"\n{len(done)} saved, {len(failed)} failed. manifest now {len(have)} products.")
    if failed:
        print("failed:", " ".join(failed))
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
