"""Who gets a gym when the pool is full.

One annotator needs one gym, and a real deployment runs a handful. The failure
this file exists for was observed, not imagined: both gyms in a two-gym pool were
held by sessions idle for 75 minutes — tabs someone had closed, which never call
/close — and every annotator opening a task got "every gym in the bridge pool is
busy". The plain TTL is 90 minutes, so the platform was down for the rest of it.

The rule under test: idleness only costs you your gym when somebody else actually
needs one, and never while you are still working.
"""

from __future__ import annotations

import time

import pytest

from tools import bridge_service as bs


@pytest.fixture()
def pool(monkeypatch):
    """A two-gym pool with no hub and no real Bridge behind it."""
    monkeypatch.setenv("GYM_URLS", "http://g1,http://g2")
    monkeypatch.setenv("BRIDGE_NO_HUB", "1")

    class _FakeBridge:
        task_id = None

        def __init__(self, **kw):
            self.gym_url = kw.get("gym_url", "")

    monkeypatch.setattr(bs, "Bridge", _FakeBridge)
    return bs._Pool()


def _age(pool, sid, seconds):
    """Backdate a session's last-touched time."""
    pool._sessions[sid].touched = time.monotonic() - seconds


def test_each_session_gets_its_own_gym(pool):
    a = pool.get("a", create=True)
    b = pool.get("b", create=True)
    assert a and b and a.gym_url != b.gym_url


def test_a_full_pool_refuses_rather_than_sharing(pool):
    """Two annotators on one gym overwrite each other's world, so a refusal the
    annotator can retry is the only honest answer."""
    pool.get("a", create=True)
    pool.get("b", create=True)
    assert pool.get("c", create=True) is None


def test_an_abandoned_session_yields_its_gym_to_a_newcomer(pool):
    """The observed outage. A closed tab never calls /close, so without this its
    gym stays leased for the full 90-minute TTL and a small pool is dead."""
    pool.get("abandoned", create=True)
    pool.get("busy", create=True)
    _age(pool, "abandoned", bs.GRACE_SEC + 60)

    got = pool.get("newcomer", create=True)
    assert got is not None, "an idle session must not block the pool"
    assert "abandoned" not in pool._sessions
    assert "busy" in pool._sessions, "only the idlest session is taken"


def test_an_active_session_is_never_evicted(pool):
    """The other half of the rule, and the one that matters more: an annotator
    mid-task must not lose their world because someone else opened a task."""
    pool.get("working", create=True)
    pool.get("also-working", create=True)
    _age(pool, "working", bs.GRACE_SEC - 30)
    _age(pool, "also-working", bs.GRACE_SEC - 10)

    assert pool.get("newcomer", create=True) is None
    assert set(pool._sessions) == {"working", "also-working"}


def test_the_idlest_session_is_the_one_taken(pool):
    pool.get("older", create=True)
    pool.get("newer", create=True)
    _age(pool, "older", bs.GRACE_SEC * 3)
    _age(pool, "newer", bs.GRACE_SEC + 5)

    pool.get("newcomer", create=True)
    assert "older" not in pool._sessions and "newer" in pool._sessions


def test_using_a_session_protects_it(pool):
    """Touch resets the clock, which is what makes 'active' mean anything."""
    pool.get("a", create=True)
    pool.get("b", create=True)
    _age(pool, "a", bs.GRACE_SEC * 2)
    pool.get("a")                       # the annotator does something

    assert pool.get("c", create=True) is None, "a just-used session is not idle"
    assert set(pool._sessions) == {"a", "b"}
