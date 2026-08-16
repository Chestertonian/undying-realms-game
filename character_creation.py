"""
Character creation flow.

Linear sequence, not a state machine — unlike LoginHandler, there's no
branching back between unrelated states (only per-step retry-on-invalid-
input loops), so a plain sequence of private methods is enough ceremony.
"""

from __future__ import annotations

from connection import Connection
from backgrounds import BACKGROUNDS
from races import RACES
from player import Player, apply_race_modifiers, create_player, name_is_taken
from stats import ATTRIBUTES, StatRoller, assign_stats

NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 16
GENDERS = ("male", "female")


class CharacterCreationHandler:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def run(self, account_id: int) -> Player:
        name = await self._prompt_name()
        race = await self._prompt_race()
        gender = await self._prompt_gender()
        background = await self._prompt_background()
        base_stats = await self._prompt_stats()

        final_stats = apply_race_modifiers(base_stats, race)

        return await create_player(
            account_id=account_id,
            name=name,
            race=race,
            gender=gender,
            background=background,
            stats=final_stats,
        )

    # --- individual steps ---

    async def _prompt_name(self) -> str:
        while True:
            await self.conn.send("Choose a character name:")
            raw = await self.conn.receive_line()
            if raw is None:
                raise ConnectionAbortedError("Connection closed during character creation.")

            name = raw.strip().capitalize()

            if not (NAME_MIN_LENGTH <= len(name) <= NAME_MAX_LENGTH) or not name.isalpha():
                await self.conn.send(
                    f"Names must be {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} letters, no numbers or symbols."
                )
                continue

            if await name_is_taken(name):
                await self.conn.send("That name is already taken.")
                continue

            return name

    async def _prompt_race(self) -> str:
        race_names = list(RACES.keys())

        await self.conn.send("--- Choose a race ---")
        for i, race in enumerate(race_names, start=1):
            mods = RACES[race]
            mod_str = " ".join(f"{attr} {mods[attr]:+d}" for attr in ATTRIBUTES)
            await self.conn.send(f"[{i}] {race} ({mod_str})")

        while True:
            raw = await self.conn.receive_line()
            if raw is None:
                raise ConnectionAbortedError("Connection closed during character creation.")
            try:
                index = int(raw.strip()) - 1
                return race_names[index]
            except (ValueError, IndexError):
                await self.conn.send("Invalid selection.")

    async def _prompt_gender(self) -> str:
        await self.conn.send("What's your gender? (male/female)")
        while True:
            raw = await self.conn.receive_line()
            if raw is None:
                raise ConnectionAbortedError("Connection closed during character creation.")
            choice = raw.strip().lower()
            if choice in GENDERS:
                return choice
            await self.conn.send("Please enter 'male' or 'female'.")

    async def _prompt_background(self) -> str:
        await self.conn.send("--- Choose a background ---")
        for i, bg in enumerate(BACKGROUNDS, start=1):
            await self.conn.send(f"[{i}] {bg}")

        while True:
            raw = await self.conn.receive_line()
            if raw is None:
                raise ConnectionAbortedError("Connection closed during character creation.")
            try:
                index = int(raw.strip()) - 1
                return BACKGROUNDS[index]
            except (ValueError, IndexError):
                await self.conn.send("Invalid selection.")

    async def _prompt_stats(self) -> dict[str, int]:
        roller = StatRoller()

        while True:
            await self.conn.send(f"Rolled: {roller.current_roll}")
            if roller.can_reroll():
                await self.conn.send(
                    f"(r)eroll [{roller.rerolls_remaining} left], (a)ssign"
                )
            else:
                await self.conn.send("No rerolls remaining. (a)ssign")

            raw = await self.conn.receive_line()
            if raw is None:
                raise ConnectionAbortedError("Connection closed during character creation.")
            choice = raw.strip().lower()

            if choice == "r" and roller.can_reroll():
                roller.reroll()
                continue
            elif choice == "a":
                return await self._prompt_assignment(roller.current_roll)
            else:
                await self.conn.send("Invalid choice.")

    async def _prompt_assignment(self, rolled_values: list[int]) -> dict[str, int]:
        while True:
            await self.conn.send(
                f"Assign your rolls ({', '.join(str(v) for v in rolled_values)}) "
                f"to attributes, in this order: {' '.join(ATTRIBUTES)}"
            )
            await self.conn.send("Example: 14 12 9 15 8 10")
            raw = await self.conn.receive_line()
            if raw is None:
                raise ConnectionAbortedError("Connection closed during character creation.")

            parts = raw.strip().split()
            if len(parts) != len(ATTRIBUTES):
                await self.conn.send(f"Enter exactly {len(ATTRIBUTES)} numbers.")
                continue

            try:
                values = [int(p) for p in parts]
            except ValueError:
                await self.conn.send("Enter numbers only.")
                continue

            assignment = dict(zip(ATTRIBUTES, values))

            try:
                return assign_stats(rolled_values, assignment)
            except ValueError as exc:
                await self.conn.send(str(exc))
                continue