"""Cycle detection and depth tracking for recursive fact evaluation."""
from __future__ import annotations

from typing import Set
from .contracts import Fact


class RecursionGuard:
    """Tracks visited fact keys along a single evaluation branch.

    A separate instance is shared down a single recursive call chain. Branches
    do NOT share state — different sub-evaluations of the same parent get
    independent copies, so common ancestors don't accidentally short-circuit
    across siblings.
    """
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self._path: Set[str] = set()

    def child(self, fact: Fact) -> "RecursionGuard":
        """Return a sibling-safe copy with `fact` marked visited."""
        nxt = RecursionGuard(max_depth=self.max_depth)
        nxt._path = self._path | {fact.key()}
        return nxt

    def has_visited(self, fact: Fact) -> bool:
        return fact.key() in self._path

    @property
    def depth(self) -> int:
        return len(self._path)

    def at_max_depth(self) -> bool:
        return self.depth >= self.max_depth


def fact_key(fact: Fact) -> str:
    """Public alias for tests."""
    return fact.key()
