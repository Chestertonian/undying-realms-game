"""
Periodic HP/SP/EP regeneration for online players.

Deliberately a separate loop from persistence.flush_loop, even though
both are periodic and both touch player state: flush_loop's job is
persistence (writing dirty state to Postgres on its own cadence),
regen_loop's job is game logic (mutating state on a gameplay-driven
cadence). Coupling them would mean changing one's interval for
persistence reasons silently changes the other's gameplay pacing, or
vice versa -- two different concerns that happen to both be periodic
should not share a clock.

Regen amount/interval here are placeholder values, not derived from any
stat or game-balance model yet -- flat +4 to each resource every 10
seconds, clamped at max. Revisit when regen mechanics are actually
designed.
"""

from __future__ import annotations

import asyncio

from player import adjust_current_hp, adjust_current_sp, adjust_current_ep
from registry import registry

REGEN_INTERVAL_SECONDS = 10
REGEN_AMOUNT = 4


async def regen_loop() -> None:
    while True:
        await asyncio.sleep(REGEN_INTERVAL_SECONDS)

        for conn in registry.connections():
            player = conn.player
            if player is None:
                continue
            adjust_current_hp(player, REGEN_AMOUNT)
            adjust_current_sp(player, REGEN_AMOUNT)
            adjust_current_ep(player, REGEN_AMOUNT)