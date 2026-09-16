"""
Reserved character-name list.

Blocks names that would collide with command verbs, movement directions,
or dispatch-ambiguous words. This is a fixed, hand-maintained list --
not derived from anything that grows over time (NPC keyword content is
handled separately by a players-vs-NPCs target-resolution precedence
rule, not by this blocklist).

TODO: Expand this at some point.
"""

from __future__ import annotations

RESERVED_NAMES: frozenset[str] = frozenset({
    # command verbs currently in the dispatch table
    "look", "quit", "say", "emote", "chat", "who", "hp", "score",

    # movement directions and common aliases
    "north", "south", "east", "west", "up", "down",
    "n", "s", "e", "w", "u", "d",

    # dispatch/targeting-ambiguous words
    "self", "me", "here", "all", "it",

    # reserved for future admin/system use
    "admin", "system", "server", "god", "test"
})


def is_reserved_name(name: str) -> bool:
    """Case-insensitive check against the reserved-name list."""
    return name.lower() in RESERVED_NAMES