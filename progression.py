"""
XP and levels. XP is a spendable pool (levels now, skills later), so every
change is a direct, atomic, relative write, and the in-memory value is always
taken from RETURNING. Neither column goes through the dirty-flag flush.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import db
from registry import registry

if TYPE_CHECKING:
    from connection import Connection

log = logging.getLogger(__name__)

MAX_LEVEL = 30


def advance_cost(level: int) -> int:
    """XP to advance from `level` to `level + 1`. Coins will join this later."""
    return 100 * level


def _find_connection(player_id: int) -> Connection | None:
    return next(
        (
            conn
            for conn in registry.connections()
            if conn.player is not None and conn.player.id == player_id
        ),
        None,
    )


async def award_xp(player_id: int, amount: int) -> None:
    """Award XP by player id. Works even if the player has disconnected;
    the in-memory player and message are handled only if still online.
    Failures are logged, not raised, so a bad write can't abort a combat tick."""
    try:
        row = await db.get_pool().fetchrow(
            "UPDATE players SET xp = xp + $1 WHERE id = $2 RETURNING xp",
            amount,
            player_id,
        )
    except Exception:
        log.exception("failed to award %d xp to player id %d", amount, player_id)
        return
    if row is None:
        return
    conn = _find_connection(player_id)
    if conn is None:
        return
    conn.player.xp = row["xp"]
    await conn.send(f"You gain {amount} experience.")


async def cmd_advance(connection: Connection, args: str) -> None:
    p = connection.player

    if p.guild_id is None or p.room.guild_id != p.guild_id:
        await connection.send("You can only advance in your own guild's hall.")
        return

    if p.level >= MAX_LEVEL:
        await connection.send("You have reached the highest level you can attain.")
        return

    cost = advance_cost(p.level)
    if p.xp < cost:
        await connection.send(
            f"You need {cost} experience to advance to level {p.level + 1}, "
            f"but you have only {p.xp}."
        )
        return

    # Atomic: succeeds only if level and XP are still what we checked.
    row = await db.get_pool().fetchrow(
        "UPDATE players SET xp = xp - $1, level = level + 1 "
        "WHERE id = $2 AND level = $3 AND xp >= $1 "
        "RETURNING xp, level",
        cost,
        p.id,
        p.level,
    )
    if row is None:
        await connection.send("You are unable to advance right now.")
        return

    p.xp, p.level = row["xp"], row["level"]
    await connection.send(f"You advance to level {p.level}!")