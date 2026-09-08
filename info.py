"""
Informational commands: who, help (later).
"""

from __future__ import annotations

from connection import Connection
from registry import registry

_NUMBER_WORDS = {
    0: "No", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
}


def _count_word(n: int) -> str:
    return _NUMBER_WORDS.get(n, str(n))


async def cmd_who(connection: Connection, args: str) -> None:
    players = sorted(
        (conn.player for conn in registry.connections() if conn.player is not None),
        key=lambda p: p.name.lower(),
    )

    await connection.send("==== Adventurers online ====")
    for p in players:
        await connection.send(f"{p.name}, {p.gender.capitalize()} {p.race.capitalize()}")

    count = len(players)
    noun = "player" if count == 1 else "players"
    summary = f"{_count_word(count)} {noun} online."
    await connection.send(summary.rjust(len(summary) + 15))
    await connection.send("=======================")