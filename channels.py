"""
Named, server-wide broadcast channels. Adding a new channel later means
adding one entry to CHANNELS plus a thin command handler.
"""

from __future__ import annotations

from dataclasses import dataclass

from connection import Connection
from registry import registry

ANSI_RESET = "\x1b[0m"


@dataclass
class Channel:
    name: str
    tag: str
    color: str  # ANSI escape code


CHANNELS: dict[str, Channel] = {
    "chat": Channel(name="chat", tag="<CHAT>", color="\x1b[36m"),  # cyan
}


async def broadcast_to_channel(channel: Channel, message: str) -> None:
    colored = f"{channel.color}{message}{ANSI_RESET}"
    for conn in registry.connections():
        if conn.player is not None:
            await conn.send(colored)


async def cmd_chat(connection: Connection, args: str) -> None:
    args = args.strip()
    if not args:
        await connection.send("Chat what?")
        return
    channel = CHANNELS["chat"]
    await broadcast_to_channel(channel, f"{connection.player.name} {channel.tag} {args}")