"""Turn an authored ShopMail corpus into the ambient mail block.

The ambient mailbox used to be ~330 one-or-two-sentence notes, which read as
obvious filler and — worse — all sat at or before May 20, so the three
pre-seeded task emails (May 21) landed at rows 1-3 of the inbox. An agent never
had to scroll or search to find the mail a task depended on.

This takes a corpus authored as {thread_key, seq, direction, day_offset, time,
...} and produces the entries `tools/ambient_catalog.build_mail` reads, with:
  * deterministic ids/threadIds (so a reseed reproduces byte-identical state),
  * real ISO timestamps on the gym's frozen clock,
  * multi-message threads that actually group,
  * a validation pass that refuses anything which could be mistaken for the
    task-relevant mail.

Usage:
    python -m tools.build_mail_corpus <authored.json> [--write] [--report]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

# The gym's frozen clock. Everything is dated relative to this.
GYM_TODAY = dt.date(2026, 5, 21)
GYM_NOW_HHMM = (12, 0)

BULK_PATH = pathlib.Path(__file__).with_name("ambient_bulk.json")

# Alice's mailbox is the ShopMail account, which is what the engine's
# MailState.account_email and tools/seed_to_cuagym.ALICE_EMAIL both say. It is
# NOT her employer's commerce domain: ShopGym is where she works and shops, and
# mixing the two silently breaks reply-all, which filters recipients by
# comparing against state.user.email.
ALICE_EMAIL = "alice@shopmail.com"

# An ambient email must never look like the mail a task turns on.
FORBIDDEN_BRANDS = ("shopgym", "valuemart", "gymeats")
TXN_WORDS = ("order confirmation", "your order", "order #", "has shipped", "out for delivery",
             "refund", "receipt for", "cancelled your", "coupon code", "price drop")
ORDER_ID_RX = re.compile(r"\b(?:ord_[a-z0-9]+|SG-\d+|VM-\d+)\b", re.I)

VALID_FOLDERS = {"inbox", "sent", "drafts", "spam", "trash", "snoozed", "archive"}
VALID_CATEGORIES = {"primary", "social", "promotions", "updates", "forums"}


def _iso(day_offset: int, time_str: str) -> str:
    d = GYM_TODAY - dt.timedelta(days=int(day_offset))
    hh, mm = (int(x) for x in time_str.split(":")[:2])
    return f"{d.isoformat()}T{hh:02d}:{mm:02d}:00"


def validate(emails: list[dict]) -> list[str]:
    """Return a list of problems. Empty list means the corpus is safe to ship."""
    problems: list[str] = []
    for i, e in enumerate(emails):
        where = f"[{i}] {e.get('subject','(no subject)')[:50]!r}"
        body = e.get("body") or ""
        subj = e.get("subject") or ""
        hay = (subj + " " + body).lower()

        if len(body) < 300:
            problems.append(f"{where}: body too short ({len(body)} chars) — no one-liners")
        if e.get("folder") not in VALID_FOLDERS:
            problems.append(f"{where}: bad folder {e.get('folder')!r}")
        if e.get("category") not in VALID_CATEGORIES:
            problems.append(f"{where}: bad category {e.get('category')!r}")

        # Day 0 is "today" — nothing may be timestamped after the frozen noon.
        try:
            hh, mm = (int(x) for x in str(e.get("time", "")).split(":")[:2])
        except Exception:
            problems.append(f"{where}: unparseable time {e.get('time')!r}")
            hh = mm = 0
        if int(e.get("day_offset", 0)) == 0 and (hh, mm) >= GYM_NOW_HHMM:
            problems.append(f"{where}: day_offset 0 at {hh:02d}:{mm:02d} is at/after the frozen noon")

        # Outgoing mail has to actually come from the mailbox owner.
        if e.get("direction") == "out" and (e.get("from_email") or "").lower() != ALICE_EMAIL:
            problems.append(f"{where}: direction 'out' but from_email is {e.get('from_email')!r}")

        # The collision rules: nothing that reads as first-party transactional mail.
        if any(b in hay for b in FORBIDDEN_BRANDS):
            if any(w in hay for w in TXN_WORDS):
                problems.append(f"{where}: first-party transactional mail — collides with task email")
        if ORDER_ID_RX.search(subj + " " + body):
            problems.append(f"{where}: contains a reserved order-id shape")
        if "alex@example.com" in hay:
            problems.append(f"{where}: uses the reserved dinner-task sender")
    return problems


def build(authored: list[dict]) -> list[dict]:
    """Assign ids, thread ids and timestamps; return ambient_bulk 'mail' entries."""
    # Stable order: thread, then position within thread. Sorting by the authored
    # key (not by arrival) keeps ids reproducible across regenerations.
    ordered = sorted(authored, key=lambda e: (str(e.get("thread_key", "")), int(e.get("seq", 1))))

    thread_ids: dict[str, str] = {}
    out: list[dict] = []
    for i, e in enumerate(ordered):
        tkey = str(e.get("thread_key") or f"solo_{i}")
        if tkey not in thread_ids:
            thread_ids[tkey] = f"amb_bthread_{len(thread_ids)}"
        out.append({
            "id": f"amb_bmail_{i}",
            "threadId": thread_ids[tkey],
            "from_name": e["from_name"], "from_email": e["from_email"],
            "to_name": e["to_name"], "to_email": e["to_email"],
            "subject": e["subject"],
            "body": e["body"],
            "timestamp": _iso(e.get("day_offset", 0), e.get("time", "09:00")),
            "folder": e.get("folder", "inbox"),
            "category": e.get("category", "primary"),
            "labels": e.get("labels") or [],
            "read": bool(e.get("read", True)),
            "starred": bool(e.get("starred", False)),
            "important": bool(e.get("important", False)),
        })
    return out


def report(entries: list[dict]) -> str:
    """Where do the pre-seeded task emails land once this corpus is in place?"""
    import collections
    lines = []
    lines.append(f"emails: {len(entries)}")
    lines.append("folders: " + str(dict(collections.Counter(e["folder"] for e in entries))))
    lines.append("categories: " + str(dict(collections.Counter(e["category"] for e in entries))))
    blens = sorted(len(e["body"]) for e in entries)
    lines.append("body chars: min=%d median=%d max=%d" % (
        blens[0], blens[len(blens) // 2], blens[-1]))
    threads = collections.Counter(e["threadId"] for e in entries)
    multi = sum(1 for v in threads.values() if v > 1)
    lines.append(f"threads: {len(threads)} ({multi} multi-message)")

    # The three pre-seeded task emails sit at 08:00 / 09:30 / 10:15 on May 21.
    inbox = sorted((e for e in entries if e["folder"] == "inbox"),
                   key=lambda e: e["timestamp"], reverse=True)
    for label, stamp in (("Welcome to ShopGym", "2026-05-21T08:00:00"),
                         ("Your weekend deals", "2026-05-21T09:30:00"),
                         ("Dinner this week?", "2026-05-21T10:15:00")):
        above = sum(1 for e in inbox if e["timestamp"] > stamp)
        lines.append(f"  task mail {label!r} would sit at inbox row {above + 1}")
    return "\n".join(lines)


DEMO_SEED = (pathlib.Path(__file__).resolve().parents[1]
             / "websites" / "xmail_mock" / "src" / "data" / "seedDefault.json")


def emit_demo_seed() -> int:
    """Regenerate the mock's standalone-demo mailbox from the same projection
    the bridged gym uses, so demo mode isn't stuck with the old filler."""
    from server.apps.mail.state import make_mailstate
    from tools.seed_to_cuagym import transform_mail

    state = transform_mail(json.loads(json.dumps(make_mailstate("m1").to_json())))
    state.pop("_gym_meta", None)
    DEMO_SEED.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    return len(state.get("emails") or [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("authored", nargs="?", help="JSON file: a list of authored emails, or {emails:[...]}")
    ap.add_argument("--write", action="store_true", help="write into tools/ambient_bulk.json")
    ap.add_argument("--demo-seed", action="store_true",
                    help="regenerate websites/xmail_mock/src/data/seedDefault.json and exit")
    args = ap.parse_args()

    if args.demo_seed and not args.authored:
        print(f"wrote {emit_demo_seed()} emails -> {DEMO_SEED}")
        return 0

    raw = json.loads(pathlib.Path(args.authored).read_text())
    authored = raw["emails"] if isinstance(raw, dict) else raw

    problems = validate(authored)
    if problems:
        print(f"REJECTED — {len(problems)} problem(s):", file=sys.stderr)
        for p in problems[:40]:
            print("  " + p, file=sys.stderr)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more", file=sys.stderr)
        return 1

    entries = build(authored)
    print(report(entries))

    if args.write:
        bulk = json.loads(BULK_PATH.read_text())
        bulk["mail"] = entries
        counts = bulk.setdefault("counts", {})
        if isinstance(counts, dict):
            counts["mail"] = len(entries)
        BULK_PATH.write_text(json.dumps(bulk, indent=1, ensure_ascii=False))
        print(f"\nwrote {len(entries)} emails -> {BULK_PATH}")
        if args.demo_seed:
            print(f"wrote {emit_demo_seed()} emails -> {DEMO_SEED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
