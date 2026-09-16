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
from movement import MOVEMENT_COMMANDS
from info import cmd_who, cmd_hp, cmd_score
from dialogue import cmd_ask

from rooms import describe_room_to, resolve_look_target

from command_types import CommandHandler

async def cmd_look(connection: Connection, args: str) -> None:
    room = connection.player.room
    target = args.strip()

    if not target:
        await describe_room_to(connection, room)
        return

    # Keywords are single-word by design (targeting.parse_target only
    # ever compares one word). Only the first token is meaningful as a
    # target — "look orc warrior" resolves the same as "look orc" rather
    # than failing outright, since trailing words are silently ignored.
    keyword = target.split(maxsplit=1)[0]

    description = await resolve_look_target(keyword, room)
    if description is None:
        await connection.send("You don't see that here.")
        return

    await connection.send(description)

async def cmd_quit(connection: Connection, args: str) -> None:
    await connection.send("Goodbye.")
    connection.player = None  # sentinel: signals the caller's loop to stop


COMMAND_TABLE: dict[str, CommandHandler] = {
    "look": cmd_look,
    "l":    cmd_look,
    "quit": cmd_quit,
    "say":  cmd_say,
    "chat": cmd_chat,
    "emote": cmd_emote,
    ";": cmd_emote,
    "who": cmd_who,
    "hp": cmd_hp,
    "score": cmd_score,
    "ask":  cmd_ask,
    **MOVEMENT_COMMANDS,
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