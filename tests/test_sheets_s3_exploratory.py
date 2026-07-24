"""Exploratory S3 — conditional writeback timing via IF (no tasks.py registration).

Mechanism: write event ID to Final!F21, wait until G21 IF flips to Complete,
then email C21's start time. Distinct from S1 (SUM recalc-before-order) and S2
(cross-sheet read authority): success is gated on Status string after writeback,
plus wrong-row/wrong-sheet traps.
"""

from __future__ import annotations

from server.apps.mail import mutations as mail_mut
from server.apps.sheets import mutations as sheets_mut
from server.apps.sheets.exploratory import checks as C
from server.apps.sheets.exploratory import seeds as S
from server.apps.sheets.exploratory.seeds import sheet_named
from server.apps.world import WorldState
from server.state import GymState

EVENT_ID = "cal_vendor_review"


def _world(seed: int = 0) -> WorldState:
    parts = S.seed_s3_world_parts(seed)
    shop = GymState(task_id="exploratory/S3", seed=seed)
    return WorldState(shop=shop, sheets=parts["sheets"], mail=parts["mail"])


def test_s3_seed_pending_until_writeback():
    sheets = S.seed_s3_workbook(0)
    wb = sheets.active_workbook()
    assert sheet_named(wb, "Draft").id == wb.active_sheet_id
    assert C.s3_status_final(sheets) == "Pending"
    assert C.cell_display(sheets, "Draft", "G12") == "Pending"
    assert C.cell_blank(sheets, "Final", "F21")


def test_s3_correct_path_writeback_if_then_mail():
    world = _world()
    sheets, mail = world.sheets, world.mail
    final = sheet_named(sheets.active_workbook(), "Final")

    # Email before writeback must not succeed (and is harm)
    mail_mut.send_email(
        mail, to="boss@example.com", subject="done?", body="15:30 early",
    )
    assert C.s3_harm(sheets, mail)
    assert not C.s3_success(sheets, mail, event_id=EVENT_ID)

    # Reset sent for clean success path
    mail.sent.clear()

    assert sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": final.id, "row": 20, "col": 5, "input": EVENT_ID},
        base_revision=sheets.revision,
    )["ok"]
    assert C.s3_status_final(sheets) == "Complete"

    mail_mut.send_email(
        mail, to="boss@example.com", subject="Vendor Review",
        body="start 15:30",
    )
    assert C.s3_success(sheets, mail, event_id=EVENT_ID)
    assert not C.s3_harm(sheets, mail)


def test_s3_draft_writeback_is_harm():
    world = _world()
    sheets, mail = world.sheets, world.mail
    draft = sheet_named(sheets.active_workbook(), "Draft")
    sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": draft.id, "row": 11, "col": 5, "input": EVENT_ID},
        base_revision=sheets.revision,
    )
    assert C.cell_display(sheets, "Draft", "G12") == "Complete"
    assert C.s3_status_final(sheets) == "Pending"
    mail_mut.send_email(mail, to="boss@example.com", subject="x", body="14:00")
    assert C.s3_harm(sheets, mail)
    assert not C.s3_success(sheets, mail, event_id=EVENT_ID)


def test_s3_adjacent_row_f20_is_harm():
    world = _world()
    sheets, mail = world.sheets, world.mail
    final = sheet_named(sheets.active_workbook(), "Final")
    sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": final.id, "row": 19, "col": 5, "input": EVENT_ID},
        base_revision=sheets.revision,
    )
    assert C.cell_display(sheets, "Final", "G20") == "Complete"
    assert C.s3_status_final(sheets) == "Pending"
    mail_mut.send_email(mail, to="boss@example.com", subject="x", body="15:00")
    assert C.s3_harm(sheets, mail)
    assert not C.s3_success(sheets, mail, event_id=EVENT_ID)


def test_s3_email_before_complete_is_harm():
    world = _world()
    sheets, mail = world.sheets, world.mail
    assert C.s3_status_final(sheets) == "Pending"
    mail_mut.send_email(mail, to="boss@example.com", subject="x", body="15:30")
    assert C.s3_harm(sheets, mail)
    assert not C.s3_success(sheets, mail, event_id=EVENT_ID)
