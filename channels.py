"""
Named, server-wide broadcast channels. Adding a new channel later means
adding one entry to CHANNELS plus a thin command handler.
"""

from __future__ import annotations

from dataclasses import dataclass

from connection import Connection
from guilds import in_guild
from registry import registry

ANSI_RESET = "\x1b[0m"


@dataclass
class Channel:
    name: str
    tag: str
    color: str  # ANSI escape code
    guild_name: str | None = None  # if set, only members may send or read
    read_staff_only: bool = False  # if set, only staff may read (and so send)
    send_staff_only: bool = False  # if set, only staff may send


CHANNELS: dict[str, Channel] = {
    "chat": Channel(name="chat", tag="<CHAT>", color="\x1b[36m"),  # cyan
    "warrior": Channel(
        name="warrior",
        tag="<WARRIOR>",
        color="\x1b[31m",  # red
        guild_name="Warriors' Guild",
    ),
    "staff": Channel(
        name="staff",
        tag="<STAFF>",
        color="\x1b[33m",  # yellow
        read_staff_only=True,
    ),
    "world": Channel(
        name="world",
        tag="<WORLD>",
        color="\x1b[35m",  # magenta
        send_staff_only=True,
    ),
}


def can_read(channel: Channel, player) -> bool:
    if channel.read_staff_only and not player.is_staff:
        return False
    if channel.guild_name is not None and not in_guild(player, channel.guild_name):
        return False
    return True


def _denial(channel: Channel, player) -> str | None:
    """Return None if the player may send, else the message to show them."""
    if not can_read(channel, player):
        # Staff-only channels are hidden from everyone else. Otherwise the
        # only remaining read restriction is the guild requirement.
        if channel.read_staff_only:
            return "Unknown command."
        return f"Only members of the {channel.guild_name} can use that channel."
    if channel.send_staff_only and not player.is_staff:
        return f"Only staff can speak on the {channel.name} channel."
    return None


async def broadcast_to_channel(channel: Channel, message: str) -> None:
    colored = f"{channel.color}{message}{ANSI_RESET}"
    for conn in registry.connections():
        if conn.player is not None and can_read(channel, conn.player):
            await conn.send(colored)


async def _speak(connection: Connection, channel: Channel, args: str) -> None:
    denial = _denial(channel, connection.player)
    if denial is not None:
        await connection.send(denial)
        return
    args = args.strip()
    if not args:
        await connection.send(f"{channel.name.capitalize()} what?")
        return
    await broadcast_to_channel(
        channel, f"{connection.player.name} {channel.tag} {args}"
    )


async def cmd_chat(connection: Connection, args: str) -> None:
    await _speak(connection, CHANNELS["chat"], args)


async def cmd_warrior(connection: Connection, args: str) -> None:
    await _speak(connection, CHANNELS["warrior"], args)


async def cmd_staff(connection: Connection, args: str) -> None:
    await _speak(connection, CHANNELS["staff"], args)


async def cmd_world(connection: Connection, args: str) -> None:
    await _speak(connection, CHANNELS["world"], args)