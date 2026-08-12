"""Mail mutations — touch ONLY MailState.

These functions never read or write the shop's ``GymState`` (or any other
app's store). The route handler is responsible for any cross-app UI
feedback (flashing on the shop state). Keeping these pure is exactly what
makes the per-app isolation test meaningful: if a mail mutation could
reach into the shop, "the agent failed in Mail" and "the shop state
changed" would be entangled and unattributable.
"""

from __future__ import annotations

from typing import Any

from server.apps.mail.state import Email, MailState, SEED_DATE


def search_inbox(mail: MailState, query: str) -> list[Email]:
    """Newest-first inbox, filtered by a case-insensitive substring match
    on subject / sender / body. Empty query returns the whole inbox."""
    q = (query or "").strip().lower()
    items = mail.ordered_inbox()
    if not q:
        return items
    return [
        e for e in items
        if q in e.subject.lower()
        or q in e.sender.lower()
        or q in e.body.lower()
    ]


def mark_read(mail: MailState, email_id: str) -> dict[str, Any]:
    """Mark an inbox email read (idempotent). Opening a message calls this
    — it is the signal a verifier reads to confirm the agent actually
    OPENED the confirmation email rather than guessing."""
    e = mail.inbox.get(email_id)
    if e is None:
        return {"ok": False, "error": "no such email"}
    e.read = True
    return {"ok": True, "email_id": email_id}


def send_email(mail: MailState, *, to: str, subject: str,
               body: str = "", cc: str = "", bcc: str = "") -> dict[str, Any]:
    """Compose-and-send. Lands a copy in the Sent folder. Validates a
    plausible recipient + non-empty subject so the agent gets a real error
    flash when it sends something malformed."""
    to = (to or "").strip()
    subject = (subject or "").strip()
    if not to or "@" not in to:
        return {"ok": False, "error": "A valid recipient email is required."}
    if not subject:
        return {"ok": False, "error": "A subject is required."}
    eid = mail.new_id()
    cc = (cc or "").strip()
    bcc = (bcc or "").strip()
    all_to = ", ".join([x for x in (to, cc, bcc) if x and x.strip()])
    mail.sent[eid] = Email(
        id=eid, sender=mail.account_email, to=all_to,
        subject=subject, body=body or "",
        received_at=f"{SEED_DATE}T12:00:00", received_label="now",
        read=True, folder="sent",
        cc=cc, bcc=bcc,
    )
    return {"ok": True, "email_id": eid, "to": to, "subject": subject,
            "cc": cc, "bcc": bcc}
