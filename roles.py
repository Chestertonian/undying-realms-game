"""
Role registry. Valid roles are defined here; the player_roles table stores
only each role's key. A role may require membership in a guild.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Role:
    key: str
    name: str
    guild_name: str | None = None


ROLES: dict[str, Role] = {
    "warrior_gm": Role(
        key="warrior_gm", name="Warrior GM", guild_name="Warriors' Guild"
    ),
}


def find_role(raw: str) -> Role | None:
    """Match 'Warrior GM', 'warrior gm', or 'warrior_gm'."""
    return ROLES.get(raw.strip().lower().replace(" ", "_"))