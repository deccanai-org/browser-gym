"""Export a gym task's seed world into the cua-hub / cua-gym `mock_states` shape.

Pipeline:  dump  ->  transform  ->  load

  dump       the gym's full per-app world for a (task_id, seed)  [reuses build_wrapped]
  transform  per app, gym shape  ->  cua-hub mock_states JSON shape
  load       mint a seed_sid per (task, mock); INSERT into cua-gym mock_states +
             an initial `set` mock_state_events row

Phase-1 pilot status:
  * dump + the MAIL transform are complete (the gmail_mock shape is known from
    real cua-gym rows).
  * shop/market/calendar/food transforms are STUBS — each needs the target
    mock_states schema from Kashyap (or read from cua-gym) before it can be filled.
  * load is DRY-RUN by default: the exact cua-gym write contract + DB access come
    from Kashyap/Ganesh. Pass --commit + CUA_GYM_DSN to actually write.

Run:
  python -m tools.seed_to_cuagym --task M1 --seed 0            # dry-run, prints JSON
  python -m tools.seed_to_cuagym --task M1 --seed 0 --app mail
  CUA_GYM_DSN=postgres://... python -m tools.seed_to_cuagym --task M1 --seed 0 --commit
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import uuid
from typing import Any, Callable

from server.seeddb._equiv import build_wrapped

# gym app key -> cua-hub mock key (the `mock` column in cua-gym.mock_state_events)
APP_TO_MOCK = {
    "shop": "amazon_mock",
    "mail": "gmail_mock",
    "market": "ebay_mock",
    "calendar": "google_calendar",
    "food": "uber_eats_mock",
}


# --------------------------------------------------------------- dump ----------
def dump_world(task_id: str, seed: int) -> dict[str, Any]:
    """The FULL per-app world for (task_id, seed) as plain dicts.

    Uses asdict (not to_json) so the whole graph is present — to_json drops the
    shop catalog and a few hidden fields, which a mock seed still needs.
    """
    return dataclasses.asdict(build_wrapped(task_id, seed))


# ----------------------------------------------------------- transforms --------
def _display_name(addr: str | None) -> str:
    if not addr:
        return ""
    local = addr.split("@", 1)[0]
    return local.replace(".", " ").replace("_", " ").title()


_GMAIL_LABELS = [
    {"id": "l1", "name": "Work", "color": "#ef4444"},
    {"id": "l2", "name": "Personal", "color": "#3b82f6"},
    {"id": "l3", "name": "Travel", "color": "#22c55e"},
    {"id": "l4", "name": "Finance", "color": "#eab308"},
]


def _iso(ts: str | None) -> str | None:
    if not ts:
        return None
    return ts if (ts.endswith("Z") or "+" in ts) else ts + "Z"


def transform_mail(mail: dict) -> dict:
    """gym MailState -> gmail_mock state (see CUA-Gym-Hub websites/gmail_mock/SCHEMA.md).

    gym:    {account_email, account_name, inbox/sent/drafts: {id: email}, ...}
    gmail:  {user:{userId,username,email,avatar}, emails:[{id, threadId, from, to:[{name,email}],
             cc, bcc, subject, body(html), timestamp, read, starred, important, labels,
             category, folder, attachments}], labels:[...], drafts:[], settings:{...}}
    """
    account = mail.get("account_email") or ""
    name = mail.get("account_name") or _display_name(account)
    emails: list[dict] = []
    for folder in ("inbox", "sent", "drafts"):
        for e in (mail.get(folder) or {}).values():
            to_addr = e.get("to") or account
            emails.append({
                "id": e.get("id"),
                "threadId": f"thread_{e.get('id')}",
                "from": {"name": _display_name(e.get("sender")), "email": e.get("sender")},
                "to": [{"name": _display_name(to_addr), "email": to_addr}],
                "cc": [],
                "bcc": [],
                "subject": e.get("subject") or "",
                "body": (e.get("body") or "").replace("\n", "<br>"),
                "timestamp": _iso(e.get("received_at")),
                "read": bool(e.get("read")),
                "starred": False,
                "important": False,
                "labels": [],
                "category": "primary",
                "folder": e.get("folder") or folder,
                "attachments": [],
            })
    return {
        "user": {"userId": "u1", "username": name, "email": account, "avatar": None},
        "emails": emails,
        "labels": list(_GMAIL_LABELS),
        "drafts": [],
        "settings": {"density": "default", "undoSend": 10},
    }


def _stub(app: str) -> Callable[[dict], dict]:
    def _t(_: dict) -> dict:
        raise NotImplementedError(
            f"transform for '{app}' ({APP_TO_MOCK[app]}) not written yet — "
            f"needs the {APP_TO_MOCK[app]} mock_states schema from Kashyap/cua-gym."
        )
    return _t


TRANSFORMERS: dict[str, Callable[[dict], dict]] = {
    "mail": transform_mail,
    "shop": _stub("shop"),
    "market": _stub("market"),
    "calendar": _stub("calendar"),
    "food": _stub("food"),
}


# ------------------------------------------------------- build seed rows -------
def build_seed_rows(task_id: str, seed: int, apps: list[str] | None = None) -> list[dict]:
    """[{mock, sid, state}] — one row per app that has a working transform."""
    world = dump_world(task_id, seed)
    want = apps or list(APP_TO_MOCK)
    rows: list[dict] = []
    for app in want:
        if app not in world:
            continue
        transform = TRANSFORMERS.get(app)
        if transform is None:
            continue
        try:
            state = transform(world[app])
        except NotImplementedError as exc:
            print(f"  skip {app}: {exc}", file=sys.stderr)
            continue
        rows.append({
            "app": app,
            "mock": APP_TO_MOCK[app],
            "sid": str(uuid.uuid4()),
            "state": state,
        })
    return rows


# ----------------------------------------------------------------- load --------
def load_rows(rows: list[dict], dsn: str) -> None:
    """INSERT each row into cua-gym: one mock_states row + one `set` event.

    Column names follow the observed cua-gym schema; confirm before committing.
    """
    import psycopg  # imported lazily so dry-run needs no driver

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            state = json.dumps(r["state"])
            cur.execute(
                "INSERT INTO mock_states (mock, sid, state) VALUES (%s, %s, %s)",
                (r["mock"], r["sid"], state),
            )
            cur.execute(
                "INSERT INTO mock_state_events (mock, sid, action, state) VALUES (%s, %s, %s, %s)",
                (r["mock"], r["sid"], "set", state),
            )
        conn.commit()


def post_rows(rows: list[dict], base_url: str, admin_token: str | None = None) -> None:
    """Seed a RUNNING mock via its state API: POST /post?sid=<sid> {action:set, state}.

    This is the canonical CUA-Gym-Hub contract (works on the mock's own dev/preview
    server). Use with --app so all rows target the one mock at base_url.
    """
    import urllib.request

    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if admin_token:
        headers["X-CUA-Admin-Token"] = admin_token
    for r in rows:
        payload = json.dumps({"action": "set", "state": r["state"]}).encode()
        req = urllib.request.Request(
            f"{base}/post?sid={r['sid']}", data=payload, method="POST", headers=headers,
        )
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
        print(f"seeded {r['mock']} sid={r['sid']} -> {body[:200]}")


# ------------------------------------------------------------------ cli --------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, help="gym task id, e.g. M1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--app", action="append", help="limit to these gym apps (repeatable)")
    ap.add_argument("--commit", action="store_true", help="write to cua-gym Postgres (needs CUA_GYM_DSN)")
    ap.add_argument("--post", metavar="URL", help="seed a running mock via POST URL/post?sid (use with --app)")
    ap.add_argument("--admin-token", help="X-CUA-Admin-Token for a hardened mock")
    args = ap.parse_args(argv)

    rows = build_seed_rows(args.task, args.seed, args.app)
    if not rows:
        print("no rows produced (no working transform for the requested apps)", file=sys.stderr)
        return 1

    if args.post:
        post_rows(rows, args.post, args.admin_token)
        return 0

    if args.commit:
        dsn = os.environ.get("CUA_GYM_DSN")
        if not dsn:
            print("--commit needs CUA_GYM_DSN in the env", file=sys.stderr)
            return 2
        load_rows(rows, dsn)
        for r in rows:
            print(f"loaded {r['mock']} seed_sid={r['sid']}")
        return 0

    # dry-run: show the mapping
    for r in rows:
        print(f"\n=== {r['app']} -> {r['mock']}  (seed_sid={r['sid']}) ===")
        print(json.dumps(r["state"], indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
