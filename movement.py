"""
Movement commands.

Each direction word (and its abbreviation) is its own exact-match verb
in the command table, but nothing is prefix-matched. All aliases for
a given direction share one handler via a small factory, since the
movement logic itself doesn't depend on which alias was typed.
"""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING
from connection import Connection
from rooms import broadcast_to_room, describe_room_to, Room
from command_types import CommandHandler
from player import adjust_current_ep
if TYPE_CHECKING:
    from combat import EntityRef

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
    adjust_current_ep(player, -2)

    await broadcast_to_room(target_room.id, f"{player.name} arrives.", exclude=[connection])
    await describe_room_to(connection, target_room)


def _make_mover(direction: str) -> CommandHandler:
    async def handler(connection: Connection, args: str) -> None:
        await do_move(connection, direction)
    return handler


def get_exits(room: "Room") -> dict[str, "Room"]:
    """Returns the room's exits as {direction: destination room},
    same shape `do_move` already reads directly off `room.exits`."""
    return room.exits

MOVEMENT_COMMANDS: dict[str, CommandHandler] = {
    alias: _make_mover(canonical) for alias, canonical in DIRECTIONS.items()
}

async def move_entity(actor: EntityRef, destination: "Room") -> None:
    """Moves `actor` to `destination`, mirroring do_move's side effects
    (leave/arrive broadcasts, room update, EP cost, room description).

    Players only, for now. combat.py's cmd_flee already passes bare
    EntityRefs, so NPC support can be added later as an `if actor[0]
    == "npc"` branch here — writing to the NpcInstance's room_id and
    broadcasting the arrival/departure, minus the EP cost and room
    description since NPCs have no Connection to describe anything
    to — without changing any call sites.
    """
    kind, player_id = actor
    if kind != "player":
        return  # TODO: NPC movement not implemented yet

    from registry import registry

    connection = None
    for conn in registry.connections():
        if conn.player is not None and conn.player.id == player_id:
            connection = conn
            break
    if connection is None:
        return  # disconnected mid-move; nothing to move

    player = connection.player
    old_room_id = player.current_room_id

    await broadcast_to_room(old_room_id, f"{player.name} leaves.", exclude=[connection])

    player.current_room_id = destination.id
    player.dirty = True
    adjust_current_ep(player, -2)

    await broadcast_to_room(destination.id, f"{player.name} arrives.", exclude=[connection])
    await describe_room_to(connection, destination)