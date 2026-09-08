"""
Room-local social commands: say, say to (later: emote, whisper).

Not modeled as Channels — their "membership" is just whoever is
standing in the room, which broadcast_to_room already expresses.
"""

from __future__ import annotations

from connection import Connection
from registry import registry
from rooms import broadcast_to_room


def find_player_in_room(room_id: int, name: str) -> Connection | None:
    name = name.lower()
    for conn in registry.connections():
        player = conn.player
        if (
            player is not None
            and player.current_room_id == room_id
            and player.name.lower() == name
        ):
            return conn
    return None


async def cmd_say(connection: Connection, args: str) -> None:
    args = args.strip()
    if not args:
        await connection.send("Say what?")
        return

    player = connection.player
    room_id = player.current_room_id

    if args.lower().startswith("to "):
        remainder = args[3:].strip()
        target_name, _, message = remainder.partition(" ")
        message = message.strip()
        if not target_name or not message:
            await connection.send("Say what, to whom?")
            return

        target_conn = find_player_in_room(room_id, target_name)
        if target_conn is None:
            await connection.send(f"There's no one here named '{target_name}'.")
            return

        if target_conn is connection:
            await connection.send(
                "You can't say something to yourself. Well, you can, but it's odd."
            )
            return

        target_player = target_conn.player
        await connection.send(f'You say to {target_player.name}, "{message}"')
        await target_conn.send(f'{player.name} says to you, "{message}"')
        await broadcast_to_room(
            room_id,
            f'{player.name} says to {target_player.name}, "{message}"',
            exclude=[connection, target_conn],
        )
        return

    await connection.send(f'You say, "{args}"')
    await broadcast_to_room(
        room_id, f'{player.name} says, "{args}"', exclude=[connection]
    )
