"""Smoke tests for Docs / Coupons / Sheets scaffolding.

Pure-logic + lightweight mutation checks — no Playwright. Confirms seed/reset
shapes and that Coupons does not invent a merchant checkout gate.
"""

from __future__ import annotations

import copy

from server.apps.coupons import mutations as coupons_mut
from server.apps.coupons.state import make_couponsstate
from server.apps.docs import mutations as docs_mut
from server.apps.docs.state import make_docsstate
from server.apps.sheets import mutations as sheets_mut
from server.apps.sheets.state import make_sheetsstate
from server.apps.world import WorldState
from server.tasks import make_task

_TASK_ID = "A1/buy_wireless_mouse"


def test_docs_seed_and_mutations():
    docs = make_docsstate(0)
    assert len(docs.documents) >= 2
    r = docs_mut.create_document(docs, title="Note", body="hello")
    assert r["ok"]
    doc = docs.get(r["doc_id"])
    assert doc is not None and doc.body == "hello"
    assert docs_mut.toggle_star(docs, r["doc_id"])["starred"] is True
    assert docs_mut.trash_document(docs, r["doc_id"])["ok"]
    assert docs.get(r["doc_id"]).folder == "trash"


def test_docs_seed_deterministic():
    a, b = make_docsstate(1), make_docsstate(1)
    assert a.to_json() == b.to_json()
    assert make_docsstate(0).to_json() != make_docsstate(1).to_json()


def test_coupons_clip_wallet_no_merchant_gate_in_mutations():
    """Merchant is metadata; clip works for every merchant label alike."""
    coupons = make_couponsstate(0)
    merchants = {o.merchant for o in coupons.offers.values()}
    assert "shop" in merchants and "market" in merchants
    for offer in coupons.ordered_offers():
        r = coupons_mut.clip_offer(coupons, offer.id)
        assert r["ok"], offer.merchant
    assert len(coupons.wallet) == len(coupons.offers)
    # Source note: apply-coupon in Shop/Market/Food must remain untouched.
    import inspect
    import server.apps.market.mutations as mm
    src = inspect.getsource(mm)
    assert "CouponOffer" not in src
    assert "coupons.wallet" not in src


def test_sheets_command_revision_and_recalc():
    sheets = make_sheetsstate(0)
    wb = sheets.active_workbook()
    assert wb is not None
    sid = wb.active_sheet_id
    snap0 = sheets_mut.snapshot_workbook(sheets)
    assert snap0["revision"] == 0
    r = sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": sid, "row": 4, "col": 0, "input": "=A2+A3"},
        base_revision=0,
        idempotency_key="k1",
    )
    assert r["ok"] and r["revision"] == 1
    cell = sheets.active_workbook().sheets[sid].get_cell(4, 0)
    assert cell.value == 15
    # Idempotent replay
    r2 = sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": sid, "row": 4, "col": 0, "input": "=A2+A3"},
        base_revision=0,
        idempotency_key="k1",
    )
    assert r2["revision"] == 1
    # Conflict
    bad = sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": sid, "row": 0, "col": 1, "input": "x"},
        base_revision=0,
    )
    assert bad["ok"] is False and "revision conflict" in bad["error"]


def test_worldstate_deepcopy_includes_new_apps():
    shop = make_task(_TASK_ID, 0)
    world = WorldState(
        shop=shop,
        docs=make_docsstate(0),
        coupons=make_couponsstate(0),
        sheets=make_sheetsstate(0),
    )
    initial = copy.deepcopy(world)
    docs_mut.create_document(world.docs, title="mut")
    coupons_mut.clip_offer(world.coupons, next(iter(world.coupons.offers)))
    sheets_mut.apply_command(
        world.sheets,
        command_type="set_cell",
        payload={
            "sheet_id": world.sheets.active_workbook().active_sheet_id,
            "row": 0, "col": 2, "input": "changed",
        },
        base_revision=0,
    )
    assert "mut" not in {
        d.title for d in initial.docs.documents.values()
    }
    assert initial.coupons.wallet == {}
    assert initial.sheets.revision == 0
    assert "docs" in world.to_json()
    assert "coupons" in world.to_json()
    assert "sheets" in world.to_json()
