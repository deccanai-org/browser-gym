"""Every product the annotator can see has a picture of something.

The annotator works through a screencast of these apps and the trajectory is sold
as a recording of someone using a real store, so a grid of coloured letter tiles
is not a cosmetic problem — it is the product looking fake. 148 of the 190
product ids the engine can produce had no photo, including the wool socks and the
camp mug, which are the items the task prompts actually name.

Two rules, and the second is why this file is not just "assert no tiles":
a product with no honest match KEEPS its tile, because a wrong photo is worse
than an obvious placeholder, and a warranty has nothing to photograph.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest

from server.seeddb import runtime
from tools import seed_to_cuagym as proj

ROOT = pathlib.Path(__file__).resolve().parents[1]

# One representative task per storefront rather than all 312 — this walks the
# real factories, and the point is the projection rule, not the catalog size.
SAMPLE = ["M100/two_recipient_expired", "M103/mixed_basket_expired", "A1/buy_wireless_mouse"]
# The multi-app breakers, which are the ones that project a shop CATALOG. A1 is a
# single-app fixture whose world has no per-app stores, so it has nothing to say
# about photo coverage — it still belongs in the broken-path check above.
WITH_CATALOG = ["M100/two_recipient_expired", "M103/mixed_basket_expired"]


def _projected(task_id: str) -> dict:
    return proj.transform_world(dataclasses.asdict(runtime.seed_source(task_id, 0)))


def _resolves(app_dir: str, url: str) -> bool:
    """A path is only real if the file is there AND is actually an image. One
    product shipped an S3 credentials error saved as .jpg, which renders as a
    blank grey box and no test noticed."""
    p = ROOT / "websites" / app_dir / "dist" / url.lstrip("/")
    if not p.exists() or p.stat().st_size < 512:
        return False
    head = p.read_bytes()[:4]
    return head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG")


@pytest.mark.parametrize("task_id", SAMPLE)
def test_no_shop_product_points_at_a_missing_or_broken_image(task_id):
    _mock, state = _projected(task_id).get("shop", (None, {}))
    bad = []
    for p in (state.get("products") or []):
        img = str(p.get("image") or "")
        if img.startswith("data:") or not img:
            continue                       # a tile is a deliberate answer
        if not _resolves("xmazon_mock", img):
            bad.append((p.get("id"), img))
    assert not bad, f"broken image paths: {bad[:6]}"


@pytest.mark.parametrize("task_id", WITH_CATALOG)
def test_almost_every_shop_product_has_a_real_photo(task_id):
    """The letter tile is the fallback, not the norm. It was the norm."""
    _mock, state = _projected(task_id).get("shop", (None, {}))
    prods = state.get("products") or []
    tiles = [p.get("id") for p in prods if str(p.get("image") or "").startswith("data:")]
    assert prods, "the projection must carry a catalog at all"
    assert len(tiles) / len(prods) < 0.15, (
        f"{len(tiles)} of {len(prods)} products fall back to a letter tile: {tiles[:8]}"
    )


def test_every_aliased_photo_actually_exists():
    """The alias map is hand-written, so a typo would put a product back on a tile
    — silently, since the fallback never errors."""
    manifest = ROOT / "tools/product_image_aliases.json"
    aliases = json.loads(manifest.read_text())
    assert aliases, "the alias map must not be empty"
    missing = {pid: base for pid, base in aliases.items()
               if not _resolves("xmazon_mock", f"/assets/products/{base}.jpg")}
    assert not missing, f"aliases pointing at files that are not there: {missing}"


def test_a_real_photo_beats_an_alias_which_beats_a_tile():
    """The precedence the whole scheme rests on: a product with its OWN photo must
    never be redirected to a shared one."""
    own = next(iter(proj._PRODUCT_IMAGES))
    assert proj._product_image(own) == f"/assets/products/{own}.jpg"

    aliased, base = next(iter(proj._IMAGE_ALIASES.items()))
    assert proj._product_image(aliased) == f"/assets/products/{base}.jpg"

    assert proj._product_image("p_not_a_real_product", "Nothing").startswith("data:image/svg")


def test_the_dumbbell_photo_is_a_photo():
    """Regression: this file was an S3 AuthorizationQueryParametersError XML saved
    with a .jpg extension — 397 bytes that render as a blank grey box on a live
    Xbay item page, and nothing anywhere checked."""
    for app in ("xmazon_mock", "xbay_mock", "xber_eats_mock"):
        assert _resolves(app, "/assets/products/amb_bl_62.jpg"), app


def test_the_build_SOURCE_holds_real_images_too():
    """Guarding dist/ alone is not enough: the next rebuild overwrites it.

    tools/build_hub_mocks.sh copies tools/product_assets/ into every storefront's
    public/, and vite copies public/ into dist/. So a corrupt file in the build
    source silently reinfects all three mocks on the next build — which is
    exactly how the dumbbell photo came back: dist/ held a good JPEG, the source
    held 397 bytes of S3 error XML, and a routine rebuild propagated the XML over
    the good copies in all three apps at once.

    Checked by magic bytes rather than extension, because the whole failure mode
    is a non-image with a .jpg on the end.
    """
    src = ROOT / "tools" / "product_assets"
    if not src.is_dir():
        pytest.skip("no vendored product assets in this checkout")

    bad = []
    for p in src.rglob("*.jpg"):
        head = p.read_bytes()[:4]
        if not (head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG")):
            bad.append(f"{p.relative_to(src)} ({p.stat().st_size} bytes)")

    assert not bad, f"the build source holds files that are not images: {bad[:6]}"
