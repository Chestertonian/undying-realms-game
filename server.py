"""
MUD server entrypoint.

Accepts telnet-compatible TCP connections, runs each one through login/
character selection, then registers the resulting player in the live
connection registry. No game loop yet — post-login is a placeholder
until rooms/dispatch exist.
"""

from __future__ import annotations

import asyncio
import logging

import db
from connection import TCPConnection
from login_handler import LoginHandler
from registry import registry

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
    log.info("Player '%s' logged in from %s", player.name, peer)

    # No game loop yet — placeholder so the connection doesn't just hang
    # or drop immediately after login. Replace once rooms/dispatch exist.
    await conn.send(f"Welcome, {player.name}. (More coming soon!)")
    async for line in conn:
        if line.strip().lower() == "quit":
            await conn.send("Goodbye.")
            break
        await conn.send(f"You said: {line}")

    registry.unregister(player.id)
    await conn.close()
    log.info("Connection closed: %s", peer)


async def main() -> None:
    await db.init_pool()
    log.info("Database pool initialized.")

    server = await asyncio.start_server(handle_client, HOST, PORT)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    log.info("Serving on %s", addrs)

    try:
        async with server:
            await server.serve_forever()
    finally:
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())