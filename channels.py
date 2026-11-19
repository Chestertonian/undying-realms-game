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
    guild_name: str | None = None  # if set, only members of this guild may send or receive


CHANNELS: dict[str, Channel] = {
    "chat": Channel(name="chat", tag="<CHAT>", color="\x1b[36m"),  # cyan
    "warrior": Channel(
        name="warrior",
        tag="<WARRIOR>",
        color="\x1b[31m",  # red
        guild_name="Warriors' Guild",
    ),
}


def can_use(channel: Channel, player) -> bool:
    return channel.guild_name is None or in_guild(player, channel.guild_name)


async def broadcast_to_channel(channel: Channel, message: str) -> None:
    colored = f"{channel.color}{message}{ANSI_RESET}"
    for conn in registry.connections():
        if conn.player is not None and can_use(channel, conn.player):
            await conn.send(colored)


async def _speak(connection: Connection, channel: Channel, args: str) -> None:
    if not can_use(channel, connection.player):
        await connection.send(
            f"Only members of the {channel.guild_name} can use that channel."
        )
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