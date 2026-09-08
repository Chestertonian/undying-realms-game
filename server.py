"""
MUD server entrypoint.

Accepts telnet-compatible TCP connections, runs each one through login/
character selection, then registers the resulting player in the live
connection registry.
"""

from __future__ import annotations

import asyncio
import logging

import db
from connection import TCPConnection
from login_handler import LoginHandler
from registry import registry
from rooms import load_rooms
from commands import *

from persistence import flush_loop

HOST = "0.0.0.0"
PORT = 4000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mud.server")


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    conn = TCPConnection(reader, writer)
    log.info("Connection opened: %s", peer)

    try:
        player = await LoginHandler(conn).run()
    except ConnectionAbortedError:
        # Connection dropped mid-login (e.g. during character creation).
        player = None

    if player is None:
        log.info("Connection closed before login completed: %s", peer)
        await conn.close()
        return

    registry.register(player.id, conn)
    conn.player = player
    log.info("Player '%s' logged in from %s", player.name, peer)

    await registry.broadcast_to_all(f"\x1b[33m<< {player.name} has entered the game. >>\x1b[0m")

    await cmd_look(conn, "")
    await conn.send_raw("> ")
    async for line in conn:
        await dispatch(conn, line)
        if conn.player is None:
            break
        await conn.send_raw("> ")

    registry.unregister(player.id)
    await conn.close()
    log.info("Connection closed: %s", peer)


async def main() -> None:
    await db.init_pool()
    log.info("Database pool initialized.")
    await load_rooms()
    log.info("Rooms loaded.")
    flush_task = asyncio.create_task(flush_loop())
    log.info("Flush loop started.")

    server = await asyncio.start_server(handle_client, HOST, PORT)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    log.info("Serving on %s", addrs)

    try:
        async with server:
            await server.serve_forever()
    finally:
        flush_task.cancel()
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())