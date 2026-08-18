"""Generate real product photos for catalog items that currently render the SVG
placeholder tile, using OpenAI gpt-image-2.

Reads the OpenAI key from .env (never prints it). For each product id it builds a
prompt from the product title/description, generates a 1024x1024 studio shot on a
white background, downscales the long edge to 800px and writes a JPEG into
tools/product_assets/products/<id>.jpg — the same folder and style as the existing
catalog photos. Then it adds the id to tools/product_images.json so the projection
resolves /assets/products/<id>.jpg instead of a gradient tile.

Idempotent: an id whose jpg already exists is skipped, so a re-run only fills gaps.

Usage:
  tools/gen_product_images.py --input /tmp/ph_products.json [--limit N] [--only id1,id2]
                              [--quality medium|high|low] [--workers 4] [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import io
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRODUCTS_DIR = ROOT / "tools" / "product_assets" / "products"
MANIFEST = ROOT / "tools" / "product_images.json"
API_URL = "https://api.openai.com/v1/images/generations"
MODEL = "gpt-image-2"


def _load_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENAI_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAI_API_KEY not found in .env")


def _prompt(prod: dict) -> str:
    title = (prod.get("title") or prod.get("name") or prod.get("id") or "").strip()
    kws = ", ".join(k for k in (prod.get("keywords") or []) if k)
    cat = (prod.get("category") or "").strip()
    extra = f" It is a {cat} product." if cat else ""
    hint = f" Visual cues: {kws}." if kws else ""
    return (
        f"A professional e-commerce catalog product photograph of: {title}.{extra}{hint} "
        "One single product, centered, filling most of the frame, shot straight on. "
        "Plain seamless pure-white studio background, soft even lighting, subtle natural "
        "contact shadow beneath the product. Photorealistic, sharp focus, true-to-life "
        "materials and colors. No text, no logos, no watermark, no props, no hands, "
        "no packaging box unless the product itself is packaging."
    )


def _generate(key: str, prompt: str, quality: str, size: str = "1024x1024") -> bytes:
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "n": 1,
        "size": size, "quality": quality,
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return base64.b64decode(data["data"][0]["b64_json"])


def _save_jpeg(png_bytes: bytes, dest: pathlib.Path, long_edge: int = 800) -> None:
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = im.size
    if max(w, h) > long_edge:
        if w >= h:
            im = im.resize((long_edge, round(h * long_edge / w)), Image.LANCZOS)
        else:
            im = im.resize((round(w * long_edge / h), long_edge), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=85, optimize=True)


def _one(key: str, prod: dict, quality: str, dry: bool) -> tuple[str, str]:
    pid = prod["id"]
    dest = PRODUCTS_DIR / f"{pid}.jpg"
    if dest.exists():
        return pid, "skip-exists"
    if dry:
        return pid, "dry-run"
    for attempt in range(4):
        try:
            png = _generate(key, _prompt(prod), quality)
            _save_jpeg(png, dest)
            return pid, "ok"
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:160]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 * (attempt + 1) ** 2)
                continue
            return pid, f"HTTP{e.code}:{msg}"
        except Exception as e:  # noqa: BLE001
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            return pid, f"{type(e).__name__}:{str(e)[:120]}"
    return pid, "give-up"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prods = json.load(open(args.input))
    if args.only:
        want = set(args.only.split(","))
        prods = [p for p in prods if p["id"] in want]
    if args.limit:
        prods = prods[: args.limit]

    key = _load_key()
    print(f"generating {len(prods)} images  model={MODEL} quality={args.quality} "
          f"workers={args.workers} dry={args.dry_run}", flush=True)

    results = {}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_one, key, p, args.quality, args.dry_run): p["id"] for p in prods}
        done = 0
        for fut in cf.as_completed(futs):
            pid, status = fut.result()
            results[pid] = status
            done += 1
            print(f"  [{done}/{len(prods)}] {pid}: {status}", flush=True)

    ok = [p for p, s in results.items() if s == "ok"]
    # add freshly-written ids to the manifest
    if ok and not args.dry_run:
        man = set(json.loads(MANIFEST.read_text())) if MANIFEST.exists() else set()
        before = len(man)
        man.update(ok)
        MANIFEST.write_text(json.dumps(sorted(man), indent=0))
        print(f"manifest: {before} -> {len(man)} (+{len(man) - before})")

    from collections import Counter
    print("summary:", dict(Counter(results.values())))
    fails = {p: s for p, s in results.items() if s not in ("ok", "skip-exists", "dry-run")}
    if fails:
        print("FAILURES:", json.dumps(fails, indent=1))
        sys.exit(1)


if __name__ == "__main__":
    main()
