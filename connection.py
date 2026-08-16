"""
Transport abstraction.

Game logic should only ever depend on the `Connection` interface below,
never on asyncio streams/sockets directly. This is what makes it cheap to
add a WebSocket transport later without touching dispatch/room/player code.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Protocol


class Connection(Protocol):
    """Minimal interface the game loop depends on."""

    async def send(self, text: str) -> None:
        """Send a line of text to the client."""
        ...

    async def receive_line(self) -> str | None:
        """
        Read one line of input from the client.
        Returns None if the connection has closed.
        """
        ...

    async def close(self) -> None:
        """Close the connection."""
        ...
        
    async def request_password_mode(self, masked: bool) -> None:
        pass  # TODO: telnet IAC WILL/WONT ECHO — deferred

    def __aiter__(self) -> AsyncIterator[str]:
        ...


class TCPConnection:
    """Connection implementation over a raw TCP socket (telnet-compatible)."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._closed = False

    async def send(self, text: str) -> None:
        if self._closed:
            return
        # \r\n is the conventional line ending for telnet-style clients.
        self._writer.write((text + "\r\n").encode("utf-8", errors="replace"))
        await self._writer.drain()

    async def receive_line(self) -> str | None:
        if self._closed:
            return None
        try:
            raw = await self._reader.readline()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            return None
        if not raw:
            # EOF: client disconnected.
            return None
        return raw.decode("utf-8", errors="replace").rstrip("\r\n")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def __aiter__(self) -> AsyncIterator[str]:
        return self._line_iterator()

    async def _line_iterator(self) -> AsyncIterator[str]:
        while True:
            line = await self.receive_line()
            if line is None:
                return
            yield line
            
    async def request_password_mode(self, masked: bool) -> None:
        pass  # TODO: telnet IAC WILL/WONT ECHO — deferred
