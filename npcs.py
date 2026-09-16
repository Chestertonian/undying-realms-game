"""
NPC templates and instances.

Existence-only milestone: NPCs are static, read-only from the server's
perspective once loaded. No dirty-flag persistence, no combat, no dialogue.

Mirrors the eager-loading approach used for rooms: load everything into
module-level dicts at startup. Unlike rooms, this is a single pass —
instances only reference templates and rooms, no forward/circular
references among NPCs themselves.

Room occupancy is scan-on-demand over `instances`, consistent with how
player room occupancy is handled in rooms.describe_room_to() — no
maintained room->NPC index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import targeting
from db import get_pool
from text_utils import pluralize


@dataclass
class NpcTemplate:
    id: int
    name: str
    description: str
    keywords: list[str]  # author-supplied, may be empty
    plural: str | None  # author-supplied override, may be None
    effective_keywords: list[str] = field(default_factory=list)  # resolved at load
    effective_plural: str = ""  # resolved at load


@dataclass
class NpcInstance:
    id: int
    template_id: int
    room_id: int


# Populated once by load_npcs() at startup; treated as read-only afterward.
templates: dict[int, NpcTemplate] = {}
instances: dict[int, NpcInstance] = {}


def _resolve_effective_keywords(template: NpcTemplate) -> list[str]:
    """
    Explicit keywords if any were authored; otherwise fall back to a
    whitespace split of the name. Resolved once at load time since this
    is static per template, not mutable state that needs re-scanning.
    """
    if template.keywords:
        return [kw.lower() for kw in template.keywords]
    return [word.lower() for word in template.name.split()]


async def load_npcs() -> None:
    """Load all NPC templates and instances from the database into the
    module-level `templates`/`instances` dicts. Call once at server
    startup, after load_rooms() (instances reference rooms by id)."""
    pool = get_pool()

    async with pool.acquire() as conn:
        template_rows = await conn.fetch(
            "SELECT id, name, description, keywords, plural FROM npc_templates"
        )
        instance_rows = await conn.fetch(
            "SELECT id, template_id, room_id FROM npc_instances"
        )

    templates.clear()
    instances.clear()

    for row in template_rows:
        template = NpcTemplate(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            keywords=list(row["keywords"]),
            plural=row["plural"],
        )
        template.effective_keywords = _resolve_effective_keywords(template)
        template.effective_plural = pluralize(template.name, template.plural)
        templates[template.id] = template

    for row in instance_rows:
        template_id = row["template_id"]
        if template_id not in templates:
            raise ValueError(
                f"npc_instances.id={row['id']} references "
                f"unknown template_id {template_id}"
            )
        instances[row["id"]] = NpcInstance(
            id=row["id"],
            template_id=template_id,
            room_id=row["room_id"],
        )


def npc_name(instance: NpcInstance) -> str:
    return templates[instance.template_id].name


def npc_description(instance: NpcInstance) -> str:
    return templates[instance.template_id].description


def npcs_in_room(room_id: int) -> list[NpcInstance]:
    """Scan-on-demand over `instances`. No maintained room->NPC index."""
    return [inst for inst in instances.values() if inst.room_id == room_id]


def npc_counts_in_room(room_id: int) -> list[tuple[NpcTemplate, int]]:
    """
    NPCs present in a room, grouped by template and counted for stacked
    display (e.g. "Two orc warriors." instead of two separate lines).
    Order follows first-appearance order in scan order (instance dict
    iteration, which is insertion/id order) — not sorted by name or count.
    """
    counts: dict[int, int] = {}
    order: list[int] = []

    for inst in npcs_in_room(room_id):
        if inst.template_id not in counts:
            counts[inst.template_id] = 0
            order.append(inst.template_id)
        counts[inst.template_id] += 1

    return [(templates[template_id], counts[template_id]) for template_id in order]


def resolve_npc_target(raw: str, room_id: int) -> NpcInstance | None:
    """
    Resolve a raw target string (e.g. "2.goblin") against the NPCs
    present in a given room. Returns None if nothing matched, whether
    because no NPC's keywords matched at all or because the requested
    ordinal exceeded the match count — callers wanting to distinguish
    those cases should call targeting.resolve_target directly with the
    same candidate list built here.

    Player names are not part of this candidate set — NPC targeting only
    ever considers NPCs.
    """
    room_instances = npcs_in_room(room_id)
    candidates = [
        (inst.id, templates[inst.template_id].effective_keywords)
        for inst in room_instances
    ]

    result = targeting.resolve_target(raw, candidates)
    if not result.found:
        return None

    return instances[result.id]