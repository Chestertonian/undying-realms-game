"""
Minimal TCP server.

Accepts telnet-compatible TCP connections and echoes input back.
No rooms, no dispatch table, no persistence yet — just proving the
connection layer works before building game logic on top of it.
"""

from __future__ import annotations

import asyncio
import logging

from connection import TCPConnection

HOST = "0.0.0.0"
PORT = 4000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mud.server")


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    conn = TCPConnection(reader, writer)
    log.info("Connection opened: %s", peer)

    await conn.send("Welcome. This is a placeholder — type anything, 'quit' to disconnect.")

    async for line in conn:
        if line.strip().lower() == "quit":
            await conn.send("Goodbye.")
            break
        await conn.send(f"You said: {line}")

    await conn.close()
    log.info("Connection closed: %s", peer)


async def main() -> None:
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    log.info("Serving on %s", addrs)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())