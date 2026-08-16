"""
Player (character) model and persistence.

Mirrors accounts.py's shape: a plain dataclass plus free functions for
DB access, rather than methods on the class itself — consistent with how
account creation/lookup is structured.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

import db
from races import RACES

STARTING_ROOM_ID = None  # TODO: set once the rooms table/seed data exists


@dataclass
class Player:
    id: int
    account_id: int
    name: str
    race: str
    gender: str
    background: str
    stats: dict[str, int]
    room_id: int | None
    created_at: datetime


def apply_race_modifiers(base_stats: dict[str, int], race: str) -> dict[str, int]:
    """
    Combine rolled+assigned base stats with the chosen race's modifiers.

    Race modifiers are currently all zero (per design decision — real
    values TBD), but this function exists now so the character-creation
    flow has one clear place stats get finalized, rather than that logic
    living inline in the prompt code. The raw pre-modifier rolls are not
    kept anywhere past this call; only the final combined stats are
    persisted, per design decision (discard rolls, don't retain them for
    later recalculation).
    """
    modifiers = RACES[race]
    return {attr: base_stats[attr] + modifiers[attr] for attr in base_stats}


async def name_is_taken(name: str) -> bool:
    pool = db.get_pool()
    row = await pool.fetchval("SELECT 1 FROM players WHERE name = $1", name)
    return row is not None


async def load_characters_for_account(account_id: int) -> list[Player]:
    pool = db.get_pool()
    rows = await pool.fetch(
        "SELECT id, account_id, name, race, gender, background, stats, room_id, created_at "
        "FROM players WHERE account_id = $1 ORDER BY created_at",
        account_id,
    )
    return [Player(**dict(row)) for row in rows]


async def load_player(player_id: int) -> Player | None:
    pool = db.get_pool()
    row = await pool.fetchrow(
        "SELECT id, account_id, name, race, gender, background, stats, room_id, created_at "
        "FROM players WHERE id = $1",
        player_id,
    )
    if row is None:
        return None
    return Player(**dict(row))


async def create_player(
    account_id: int,
    name: str,
    race: str,
    gender: str,
    background: str,
    stats: dict[str, int],
) -> Player:
    pool = db.get_pool()
    try:
        row = await pool.fetchrow(
            "INSERT INTO players (account_id, name, race, gender, background, stats, room_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "RETURNING id, account_id, name, race, gender, background, stats, room_id, created_at",
            account_id,
            name,
            race,
            gender,
            background,
            stats,
            STARTING_ROOM_ID,
        )
    except asyncpg.UniqueViolationError as exc:
        # Character name already taken; caller is expected to have already
        # checked name_is_taken(), so this is a safety net against races,
        # same pattern as create_account() in accounts.py.
        raise ValueError(f"Character creation failed: {exc}") from exc

    return Player(**dict(row))