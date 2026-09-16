"""
Room loading and in-memory room registry.

Rooms are loaded 'eagerly' at startup into a dict[int, Room]. Exits are
resolved in a second pass once all rooms exist, so Room.exits holds live
Room references rather than bare IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from registry import registry

from connection import Connection

from db import get_pool

import npcs
import targeting
from text_utils import number_to_words


@dataclass
class Room:
    id: int
    name: str
    description: str
    exits: dict[str, "Room"] = field(default_factory=dict)


# Populated once by load_rooms() at startup; treated as read-only afterward.
rooms: dict[int, Room] = {}


async def load_rooms() -> None:
    """Load all rooms and exits from the database into the module-level
    `rooms` dict. Call once at server startup, after init_pool()."""
    pool = get_pool()

    async with pool.acquire() as conn:
        room_rows = await conn.fetch("SELECT id, name, description FROM rooms")
        exit_rows = await conn.fetch(
            "SELECT room_id, direction, target_room_id FROM exits"
        )

    rooms.clear()
    for row in room_rows:
        rooms[row["id"]] = Room(
            id=row["id"],
            name=row["name"],
            description=row["description"],
        )

    for row in exit_rows:
        room_id = row["room_id"]
        target_id = row["target_room_id"]

        if room_id not in rooms:
            raise ValueError(f"Exit references unknown room_id {room_id}")
        if target_id not in rooms:
            raise ValueError(f"Exit references unknown target_room_id {target_id}")

        rooms[room_id].exits[row["direction"]] = rooms[target_id]
        
async def broadcast_to_room(room_id: int, message: str, exclude: list[Connection] | None = None) -> None:
    exclude = exclude or []
    for conn in registry.connections():
        player = conn.player
        if player is None or player.current_room_id != room_id or conn in exclude:
            continue
        await conn.send(message)
        
async def describe_room_to(connection: Connection, room: Room) -> None:
    await connection.send(room.name)
    await connection.send(room.description)

    occupant_lines = []

    others = [
        conn.player.name
        for conn in registry.connections()
        if conn.player is not None
        and conn is not connection
        and conn.player.current_room_id == room.id
    ]
    occupant_lines.extend(f"{name}." for name in sorted(others))

    for template, count in npcs.npc_counts_in_room(room.id):
        if count == 1:
            name = template.name
            occupant_lines.append(f"{name[0].upper()}{name[1:]}.")
        else:
            count_word = number_to_words(count)
            occupant_lines.append(
                f"{count_word[0].upper()}{count_word[1:]} {template.effective_plural}."
            )

    if occupant_lines:
        await connection.send("")
        await connection.send("\n".join(occupant_lines))

    if room.exits:
        await connection.send("Exits: " + ", ".join(sorted(room.exits)))
    else:
        await connection.send("There are no obvious exits.")


async def resolve_look_target(raw: str, room: Room) -> str | None:
    """
    Resolve a `look <target>` argument against the NPCs present in a
    room. Returns the NPC's description, or None if nothing matched.

    Player-name and self-look resolution are handled elsewhere in the
    look command's dispatch (not here) — this function only covers the
    NPC case. Ordering relative to player-name resolution doesn't
    matter: NPC keywords never collide with player names, since player
    names are excluded from NPC keyword space by construction.
    """
    instance = npcs.resolve_npc_target(raw, room.id)
    if instance is None:
        return None
    return npcs.npc_description(instance)