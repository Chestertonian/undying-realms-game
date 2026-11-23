"""
Informational commands: who, help (later).
"""

from __future__ import annotations

from connection import Connection
from registry import registry
import guilds
from roles import *
import logging
log = logging.getLogger(__name__)

HEADERS = ("Name", "Gender", "Race", "Guild", "Title")

_NUMBER_WORDS = {
    0: "No",
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
}


def _count_word(n: int) -> str:
    return _NUMBER_WORDS.get(n, str(n))


async def cmd_who(connection: Connection, args: str) -> None:
    #TODO - titles not showing up
    players = sorted(
        (
            conn.player
            for conn in registry.connections()
            if conn.player is not None and not conn.player.is_staff
        ),
        key=lambda p: p.name.lower(),
    )

    rows = [
        (
            p.name,
            p.gender.capitalize(),
            p.race.capitalize(),
            guilds.guild_name(p.guild_id) if p.guild_id is not None else "-",
            ", ".join(role_names(p.roles)) or "-",
        )
        for p in players
    ]

    from roles import ROLES  # temporary
    for p in players:
        log.warning(
            "who debug: %s guild_id=%r roles=%r names=%r registry=%r",
            p.name, p.guild_id, p.roles, role_names(p.roles), list(ROLES),
        )

    col_w = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(HEADERS)]

    def fmt(cells) -> str:
        return ("  " + "   ".join(c.ljust(w) for c, w in zip(cells, col_w))).rstrip()

    header = " Adventurers Online "
    width = max(len(header) + 4, len(fmt(HEADERS)))
    border = "=" * width

    await connection.send(border)
    await connection.send(header.center(width, "="))
    await connection.send(border)
    await connection.send(fmt(HEADERS))
    await connection.send("-" * width)

    for r in rows:
        await connection.send(fmt(r))

    count = len(rows)
    noun = "player" if count == 1 else "players"
    await connection.send(border)
    await connection.send(f"{_count_word(count)} {noun} online.".center(width))

async def cmd_hp(connection: Connection, args: str) -> None:
    p = connection.player
    await connection.send(
        f"HP: {p.current_hp}/{p.max_hp}   SP: {p.current_sp}/{p.max_sp}   EP: {p.current_ep}/{p.max_ep}"
    )


async def cmd_score(connection: Connection, args: str) -> None:
    p = connection.player
    width = 44

    def row(label: str, value: str) -> str:
        return f"  {label:<12}{value}"

    guild_rows = (
        [row("Guild:", guilds.guild_name(p.guild_id))] if p.guild_id is not None else []
    )

    lines = [
        "=" * width,
        " Character Sheet ".center(width, "="),
        "=" * width,
        row("Name:", p.name),
        row("Race:", p.race.capitalize()),
        row("Gender:", p.gender.capitalize()),
        row("Background:", p.background),
        *guild_rows,
        row("Level:", str(p.level)),
        row("XP:", str(p.xp)),
        "-" * width,
        row("STR:", str(p.stats["STR"])),
        row("DEX:", str(p.stats["DEX"])),
        row("CON:", str(p.stats["CON"])),
        row("INT:", str(p.stats["INT"])),
        row("WIS:", str(p.stats["WIS"])),
        row("CHA:", str(p.stats["CHA"])),
        "-" * width,
        row("HP:", f"{p.current_hp}/{p.max_hp}"),
        row("SP:", f"{p.current_sp}/{p.max_sp}"),
        row("EP:", f"{p.current_ep}/{p.max_ep}"),
        "=" * width,
    ]
    for line in lines:
        await connection.send(line)
