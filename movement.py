"""
Movement commands.

Each direction word (and its abbreviation) is its own exact-match verb
in the command table, but nothing is prefix-matched. All aliases for
a given direction share one handler via a small factory, since the
movement logic itself doesn't depend on which alias was typed.
"""

from __future__ import annotations

from connection import Connection
from rooms import broadcast_to_room, describe_room_to
from command_types import CommandHandler

# alias -> canonical direction name, matching the exit strings used in
# the exits table / seed data.
DIRECTIONS: dict[str, str] = {
    "north": "north", "n": "north",
    "south": "south", "s": "south",
    "east": "east", "e": "east",
    "west": "west", "w": "west",
    "up": "up", "u": "up",
    "down": "down", "d": "down",
    "northeast": "northeast", "ne": "northeast",
    "northwest": "northwest", "nw": "northwest",
    "southeast": "southeast", "se": "southeast",
    "southwest": "southwest", "sw": "southwest",
}


async def do_move(connection: Connection, direction: str) -> None:
    player = connection.player
    room = player.room

    target_room = room.exits.get(direction)
    if target_room is None:
        await connection.send("You can't go that way.")
        return

    old_room_id = player.current_room_id
    await broadcast_to_room(old_room_id, f"{player.name} leaves.", exclude=[connection])

    player.current_room_id = target_room.id
    player.dirty = True

    await broadcast_to_room(target_room.id, f"{player.name} arrives.", exclude=[connection])
    await describe_room_to(connection, target_room)


def _make_mover(direction: str) -> CommandHandler:
    async def handler(connection: Connection, args: str) -> None:
        await do_move(connection, direction)
    return handler


MOVEMENT_COMMANDS: dict[str, CommandHandler] = {
    alias: _make_mover(canonical) for alias, canonical in DIRECTIONS.items()
}