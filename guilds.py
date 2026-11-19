"""
Guilds: exclusive, permanent membership. A room with a non-NULL guild_id is
that guild's hall; `join` there joins that guild.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import db

if TYPE_CHECKING:
    from connection import Connection


@dataclass
class Guild:
    id: int
    name: str
    description: str


guilds: dict[int, Guild] = {}


async def load_guilds() -> None:
    """Load all guilds into the module-level `guilds` dict. Call once at
    startup, after init_pool()."""
    pool = db.get_pool()
    rows = await pool.fetch("SELECT id, name, description FROM guilds")
    guilds.clear()
    for row in rows:
        guilds[row["id"]] = Guild(**dict(row))


def guild_name(guild_id: int) -> str:
    return guilds[guild_id].name


async def cmd_join(connection: Connection, args: str) -> None:
    p = connection.player

    hall_guild_id = p.room.guild_id
    if hall_guild_id is None:
        await connection.send("There is no guild to join here.")
        return

    guild = guilds[hall_guild_id]

    if p.guild_id is not None:
        if p.guild_id == hall_guild_id:
            await connection.send(f"You are already a member of the {guild.name}.")
        else:
            await connection.send("You already belong to a guild.")
        return

    if args.strip().lower() != "confirm":
        await connection.send(
            f"Joining the {guild.name} is permanent. You will never be able "
            "to leave it or join another guild."
        )
        await connection.send("Type 'join confirm' to proceed.")
        return

    # Atomic: succeeds only if the player is still unguilded.
    result = await db.get_pool().execute(
        "UPDATE players SET guild_id = $1 WHERE id = $2 AND guild_id IS NULL",
        hall_guild_id,
        p.id,
    )
    if result != "UPDATE 1":
        await connection.send("You already belong to a guild.")
        return

    p.guild_id = hall_guild_id  # in-memory update only after the write succeeds
    await connection.send(f"You have joined the {guild.name}.")