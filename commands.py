"""
Command dispatch.

Commands are matched by exact verb, not prefix — deliberately, to avoid
accidental invocation from typos or truncated input (e.g. "lo" should
not silently run "look").
"""

from __future__ import annotations

from typing import Awaitable, Callable

from connection import Connection

from registry import registry

from social import cmd_say, cmd_emote
from channels import cmd_chat 

CommandHandler = Callable[[Connection, str], Awaitable[None]]


async def cmd_look(connection: Connection, args: str) -> None:
    room = connection.player.room
    await connection.send(room.name)
    await connection.send(room.description)
    
    others = [
        conn.player.name
        for conn in registry.connections()
        if conn.player is not None
        and conn is not connection
        and conn.player.current_room_id == room.id
    ]
    
    if others:
        await connection.send("Also here: " + ", ".join(sorted(others)))

    if room.exits:
        await connection.send("Exits: " + ", ".join(sorted(room.exits)))
    else:
        await connection.send("There are no obvious exits.")


async def cmd_quit(connection: Connection, args: str) -> None:
    await connection.send("Goodbye.")
    connection.player = None  # sentinel: signals the caller's loop to stop


COMMAND_TABLE: dict[str, CommandHandler] = {
    "look": cmd_look,
    "quit": cmd_quit,
    "say":  cmd_say,
    "chat": cmd_chat,
    "emote": cmd_emote,
    ";": cmd_emote,
}


async def dispatch(connection: Connection, line: str) -> None:
    verb, _, args = line.strip().partition(" ")
    verb = verb.lower()
    if not verb:
        return

    handler = COMMAND_TABLE.get(verb)
    if handler is None:
        await connection.send("Unknown command.")
        return

    await handler(connection, args)