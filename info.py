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

    rows = [(p.name, p.gender.capitalize(), p.race.capitalize()) for p in players]

    name_w = max((len(r[0]) for r in rows), default=4)
    gender_w = max((len(r[1]) for r in rows), default=6)

    header = " Adventurers Online "
    width = max(len(header) + 4, name_w + gender_w + 12)
    border = "=" * width

    await connection.send(border)
    await connection.send(header.center(width, "="))
    await connection.send(border)

    for name, gender, race in rows:
        line = f"  {name.ljust(name_w)}   {gender.ljust(gender_w)}   {race}"
        await connection.send(line)

    count = len(rows)
    noun = "player" if count == 1 else "players"
    await connection.send(border)
    await connection.send(f"{_count_word(count)} {noun} online.".center(width))