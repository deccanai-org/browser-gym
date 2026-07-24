"""Docs app — an isolated documents client at the ``/docs`` route family.

Owns its own store (:class:`server.apps.docs.state.DocsState`). Mutations
touch ONLY that store; cross-app effects arrive through the event bus, never
by another app writing here directly.
"""
