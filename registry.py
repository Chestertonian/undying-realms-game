"""
Live connection registry.

Tracks which characters are currently connected, keyed by player_id.
This is what makes duplicate-login detection possible (LoginHandler
checks is_online() before letting a character log in a second time)
and will be reused later for NPC visibility and combat targeting, per
the roadmap — anything that needs to know "who's actually in the game
right now" goes through this.
"""

from __future__ import annotations

from connection import Connection


class ConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[int, Connection] = {}

    def is_online(self, player_id: int) -> bool:
        return player_id in self._connections

    def register(self, player_id: int, conn: Connection) -> None:
        self._connections[player_id] = conn

    def unregister(self, player_id: int) -> None:
        self._connections.pop(player_id, None)

    def get_connection(self, player_id: int) -> Connection | None:
        return self._connections.get(player_id)

    async def kick(self, player_id: int) -> None:
        """
        Forcibly disconnect a character's existing session.

        Goes through the same teardown a normal disconnect would (close
        the connection, then unregister) rather than a special-cased
        force-close, per design decision — keeps this path unified with
        whatever normal disconnect handling looks like once it exists.
        """
        conn = self._connections.get(player_id)
        if conn is None:
            return
        await conn.send("You have been disconnected: logged in elsewhere.")
        await conn.close()
        self.unregister(player_id)


# Single shared instance, module-level — mirrors db.py's pattern of
# holding shared state at module scope rather than passing it explicitly
# through every function that needs it.
registry = ConnectionRegistry()