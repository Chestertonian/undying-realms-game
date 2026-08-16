"""
Stat rolling for character creation.

Method: 4d6 drop lowest.
Rolling produces an unlabeled list of six values.
This module only handles the dice, not assignment.
"""

from __future__ import annotations

import random

ATTRIBUTES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
MAX_REROLLS = 10


def roll_4d6_drop_lowest() -> int:
    rolls = [random.randint(1, 6) for _ in range(4)]
    return sum(rolls) - min(rolls)


def roll_stats() -> list[int]:
    """Roll six attribute values (unassigned, unlabeled)."""
    return [roll_4d6_drop_lowest() for _ in range(6)]


class StatRoller:
    """
    Tracks reroll count across a single character-creation session.

    A fresh instance should be created per character being made — the
    10-reroll cap is per character, not per account or lifetime, per
    design discussion (resets every time someone starts creating a new
    character).
    """

    def __init__(self) -> None:
        self.rerolls_used = 0
        self.current_roll: list[int] = roll_stats()

    @property
    def rerolls_remaining(self) -> int:
        return MAX_REROLLS - self.rerolls_used

    def can_reroll(self) -> bool:
        return self.rerolls_used < MAX_REROLLS

    def reroll(self) -> list[int]:
        if not self.can_reroll():
            raise ValueError("No rerolls remaining.")
        self.rerolls_used += 1
        self.current_roll = roll_stats()
        return self.current_roll


def assign_stats(rolled_values: list[int], assignment: dict[str, int]) -> dict[str, int]:
    """
    Validate and build the final stats dict from a player's chosen
    assignment of rolled values to attributes.

    `assignment` maps attribute name -> chosen value, e.g.
    {"STR": 14, "DEX": 9, "CON": 12, "INT": 10, "WIS": 8, "CHA": 15}.
    Every attribute must be present exactly once, and the multiset of
    assigned values must exactly match the multiset of rolled values —
    this catches typos or attempts to assign a value that wasn't rolled.
    """
    if set(assignment.keys()) != set(ATTRIBUTES):
        raise ValueError(f"Assignment must cover exactly: {ATTRIBUTES}")

    if sorted(assignment.values()) != sorted(rolled_values):
        raise ValueError("Assigned values must exactly match the rolled values.")

    return dict(assignment)