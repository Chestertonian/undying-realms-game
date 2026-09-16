"""
NPC dialogue: template-scoped topic -> response lookup for
`ask <npc> about <topic>`.

Eager-loaded at startup into a module-level dict, same pattern as
npcs.py and rooms.py. Read-only after load -- no dirty-flag persistence,
consistent with how NPCs are handled generally.

Topic matching is exact-match on the full string following "about"
(lowercased, trimmed) -- not tokenized to a single word. Unlike NPC
name keywords, which need single-word tokens to support "goblin" AND
"soldier" both matching "Goblin soldier", dialogue topics aren't tied
to disambiguating a display name, so there's no reason to restrict
authors to one-word topics.
"""

from __future__ import annotations

from connection import Connection
from db import get_pool
import npcs

# Keyed by (template_id, keyword), keyword lowercased at load.
_responses: dict[tuple[int, str], str] = {}


async def load_dialogue() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT template_id, keyword, response FROM npc_dialogue"
        )

    _responses.clear()
    for row in rows:
        _responses[(row["template_id"], row["keyword"].lower())] = row["response"]


def get_response(template_id: int, topic: str) -> str | None:
    return _responses.get((template_id, topic.lower()))


async def cmd_ask(connection: Connection, args: str) -> None:
    player = connection.player
    room = player.room

    lowered = args.lower()
    idx = lowered.find(" about ")
    if idx == -1:
        await connection.send("Ask whom about what? Try: ask <npc> about <topic>")
        return

    npc_part = args[:idx].strip()
    topic = args[idx + len(" about "):].strip()

    if not npc_part or not topic:
        await connection.send("Ask whom about what? Try: ask <npc> about <topic>")
        return

    instance = npcs.resolve_npc_target(npc_part, room.id)
    if instance is None:
        await connection.send("You don't see that here.")
        return

    response = get_response(instance.template_id, topic)
    if response is None:
        name = npcs.npc_name(instance)
        response = f"{name[0].upper()}{name[1:]} doesn't seem to know anything about that."

    await connection.send(response)