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
    """A two-gym pool with no hub and no real Bridge behind it.

    Autoscaling is OFF here on purpose. These tests are about the EVICTION policy
    when the pool is at its ceiling; with growth enabled a "full" pool would start
    a real uvicorn instead, which is a different behaviour with its own tests
    below."""
    monkeypatch.setenv("GYM_URLS", "http://g1,http://g2")
    monkeypatch.setenv("BRIDGE_NO_HUB", "1")
    monkeypatch.setattr(bs, "AUTOSCALE", False)

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


# --------------------------------------------------------------------------- growth

def test_the_pool_grows_before_it_refuses_an_annotator(monkeypatch):
    """One annotator needs one gym, so two static gyms meant the third annotator
    was simply told to come back later — and since a certify leases a second gym
    it was really the SECOND annotator. Isolation is the point; the answer is to
    have enough gyms, not to share one.
    """
    started: list[str] = []

    class _FakeBridge:
        task_id = None
        def __init__(self, **kw): self.gym_url = kw.get("gym_url", "")

    monkeypatch.setenv("GYM_URLS", "http://g1,http://g2")
    monkeypatch.setenv("BRIDGE_NO_HUB", "1")
    monkeypatch.setattr(bs, "Bridge", _FakeBridge)
    monkeypatch.setattr(bs, "AUTOSCALE", True)

    def _fake_grow():
        url = f"http://grown{len(started)}"
        started.append(url)
        bs._GROWN[url] = object()          # so _gym_pool() reports it
        return url

    monkeypatch.setattr(bs, "_grow_pool", _fake_grow)
    monkeypatch.setattr(bs, "_GROWN", {})

    pool = bs._Pool()
    a, b = pool.get("a", create=True), pool.get("b", create=True)
    c = pool.get("c", create=True)          # would have been refused before

    assert c is not None, "a third annotator must get a gym, not a 503"
    assert len({a.gym_url, b.gym_url, c.gym_url}) == 3, "and it must be their OWN gym"
    assert started == ["http://grown0"]


def test_growth_stops_at_the_ceiling_rather_than_filling_the_host(monkeypatch):
    """A world per annotator is bounded, not unlimited — an unbounded acquire
    loop fills the machine instead of merely breaking a policy."""
    class _FakeBridge:
        task_id = None
        def __init__(self, **kw): self.gym_url = kw.get("gym_url", "")

    monkeypatch.setenv("GYM_URLS", "http://g1")
    monkeypatch.setenv("BRIDGE_NO_HUB", "1")
    monkeypatch.setattr(bs, "Bridge", _FakeBridge)
    monkeypatch.setattr(bs, "AUTOSCALE", True)
    monkeypatch.setattr(bs, "MAX_GYMS", 2)
    monkeypatch.setattr(bs, "_GROWN", {})

    real_grow = bs._grow_pool
    def _fake_grow():
        # Mirror the real cap check without starting a process.
        if len(bs._gym_pool()) >= bs.MAX_GYMS:
            return None
        url = f"http://grown{len(bs._GROWN)}"
        bs._GROWN[url] = object()
        return url
    monkeypatch.setattr(bs, "_grow_pool", _fake_grow)

    pool = bs._Pool()
    assert pool.get("a", create=True) is not None      # static g1
    assert pool.get("b", create=True) is not None      # grown to the cap of 2
    assert pool.get("c", create=True) is None, "at the ceiling it must still refuse"


def test_a_grown_gym_is_reused_after_its_session_closes(monkeypatch):
    """Growth is not per-session leakage: a gym that has been started stays in the
    pool and the next annotator gets it, so the process count settles at the
    high-water mark rather than climbing forever."""
    class _FakeBridge:
        task_id = None
        def __init__(self, **kw): self.gym_url = kw.get("gym_url", "")

    monkeypatch.setenv("GYM_URLS", "http://g1")
    monkeypatch.setenv("BRIDGE_NO_HUB", "1")
    monkeypatch.setattr(bs, "Bridge", _FakeBridge)
    monkeypatch.setattr(bs, "AUTOSCALE", True)
    monkeypatch.setattr(bs, "_GROWN", {})
    grows = []
    def _fake_grow():
        url = f"http://grown{len(grows)}"
        grows.append(url)
        bs._GROWN[url] = object()
        return url
    monkeypatch.setattr(bs, "_grow_pool", _fake_grow)

    pool = bs._Pool()
    pool.get("a", create=True)
    pool.get("b", create=True)          # grows one
    pool.close("b")
    pool.get("c", create=True)          # must REUSE it, not grow again

    assert len(grows) == 1, f"a second gym was started needlessly: {grows}"


def test_growing_the_pool_does_not_deadlock_on_its_own_lock():
    """`_grow_pool` holds the grown-set lock while it checks the cap, and the cap
    check reads the pool, which takes the same lock. With a plain Lock that is a
    deadlock — the bridge froze on the first annotator who needed a third gym,
    which is exactly the case the growth code exists to serve. Caught live, not
    by the mocked tests above, because they replaced `_grow_pool` wholesale."""
    import threading as _t

    assert isinstance(bs._GROWN_LOCK, _t.RLock().__class__), (
        "_GROWN_LOCK must be reentrant: _grow_pool -> _gym_pool re-enters it"
    )

    # And prove it by actually re-entering, with a watchdog so a regression fails
    # the test instead of hanging the suite.
    done = _t.Event()

    def _reenter():
        with bs._GROWN_LOCK:
            bs._gym_pool()          # takes it again
        done.set()

    th = _t.Thread(target=_reenter, daemon=True)
    th.start()
    assert done.wait(timeout=5), "re-entering the grown lock deadlocked"


def test_a_grown_gym_is_placed_clear_of_the_published_service_ports():
    """Walking upward from 8077 put a "gym" on 8080 — the annotator frontend —
    and the pool then leased the frontend to an annotator as their world."""
    taken = {8080, 8090, 8093, 5201, 5202, 5203, 5204, 5205, 8877}
    span = range(bs.GROW_PORT_BASE, bs.GROW_PORT_BASE + bs.MAX_GYMS * 4)
    assert not (taken & set(span)), (
        f"the grow range {span.start}-{span.stop} overlaps published ports {sorted(taken & set(span))}"
    )


def test_something_that_merely_speaks_http_is_not_accepted_as_a_gym(monkeypatch):
    """The other half of that bug: the readiness probe took any HTTP answer as a
    ready gym, so a port collision became a correctness problem rather than a
    loud failure. A gym is identified by its own routes."""
    import io, urllib.error

    def _frontend(url, timeout=0):
        # An SPA answers 200 with HTML on every path, openapi.json included.
        return io.BytesIO(b"<!doctype html><html></html>")

    monkeypatch.setattr(bs.urllib.request, "urlopen", _frontend)
    assert bs._is_a_gym("http://127.0.0.1:8080") is False

    def _gym(url, timeout=0):
        return io.BytesIO(b'{"paths": {"/_harness/tasks": {}, "/mock/shop": {}}}')

    monkeypatch.setattr(bs.urllib.request, "urlopen", _gym)
    assert bs._is_a_gym("http://127.0.0.1:8300") is True
