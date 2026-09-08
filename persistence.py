"""
Generic dirty-flag flush loop.

This file owns the tick and the list of flush functions to call each
tick -- nothing else. Each entity type (players now; rooms, NPCs, items
later) owns its own scan-and-write logic in its own module. Adding a new
persisted entity type later means writing its flush function elsewhere
and appending it to FLUSH_FUNCTIONS below -- no changes to the loop
itself.
"""

from __future__ import annotations

import asyncio
import logging

from player import flush_dirty_players

log = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS = 1.0

FLUSH_FUNCTIONS = [
    flush_dirty_players,
]


async def flush_loop() -> None:
    """
    Runs forever, ticking every FLUSH_INTERVAL_SECONDS. A failure in one
    flush function is logged and skipped rather than allowed to crash
    the loop or block other entity types from flushing on the same tick
    -- one bad write shouldn't stop everything else from saving.
    """
    while True:
        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
        for flush_fn in FLUSH_FUNCTIONS:
            try:
                await flush_fn()
            except Exception:
                log.exception("Flush function %s failed", flush_fn.__name__)