"""
Item templates and instances.

Templates carry static data (name, description, keywords, type). Instances
currently carry only location — no mutable state. Type-specific mutable state 
(e.g. torch charges) will live in future per-type sidecar tables keyed by
instance id, not on item_instances itself.

Mirrors the eager-loading approach used for NPCs and rooms: load
everything into module-level dicts at startup.

Item location ("room" vs "player") is a scan-on-demand lookup over
`instances`, consistent with npcs_in_room()/players_in_room() — no
maintained room->item or player->item index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import targeting
from db import get_pool
from text_utils import pluralize


@dataclass
class ItemTemplate:
    id: int
    name: str
    description: str
    keywords: list[str]
    plural: str | None
    type: str
    effective_keywords: list[str] = field(default_factory=list)
    effective_plural: str = ""


@dataclass
class ItemInstance:
    id: int
    template_id: int
    location_kind: str  # 'room' | 'player'
    location_id: int


# Populated once by load_items() at startup; treated as read-only afterward
# except for location_kind/location_id, which move_item() mutates in
# place and writes through immediately.
templates: dict[int, ItemTemplate] = {}
instances: dict[int, ItemInstance] = {}


def _resolve_effective_keywords(template: ItemTemplate) -> list[str]:
    """
    Explicit keywords, plus the item's type as an implicit keyword (a
    sword with type "weapon" also responds to "weapon"; a generic object
    with type "generic" also responds to "generic"). Unlike NPCs, there
    is no whitespace-split-of-name fallback — item keywords are always
    explicit, plus this one implicit addition.
    """
    keywords = [kw.lower() for kw in template.keywords]
    type_keyword = template.type.lower()
    if type_keyword not in keywords:
        keywords.append(type_keyword)
    return keywords


async def load_items() -> None:
    """Load all item templates and instances from the database into the
    module-level `templates`/`instances` dicts. Call once at server
    startup, after load_rooms()."""
    pool = get_pool()

    async with pool.acquire() as conn:
        template_rows = await conn.fetch(
            "SELECT id, name, description, keywords, plural, type "
            "FROM item_templates"
        )
        instance_rows = await conn.fetch(
            "SELECT id, template_id, location_kind, location_id "
            "FROM item_instances"
        )

    templates.clear()
    instances.clear()

    for row in template_rows:
        template = ItemTemplate(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            keywords=list(row["keywords"]),
            plural=row["plural"],
            type=row["type"],
        )
        template.effective_keywords = _resolve_effective_keywords(template)
        template.effective_plural = pluralize(template.name, template.plural)
        templates[template.id] = template

    for row in instance_rows:
        template_id = row["template_id"]
        if template_id not in templates:
            raise ValueError(
                f"item_instances.id={row['id']} references "
                f"unknown template_id {template_id}"
            )
        instances[row["id"]] = ItemInstance(
            id=row["id"],
            template_id=template_id,
            location_kind=row["location_kind"],
            location_id=row["location_id"],
        )


def item_name(instance: ItemInstance) -> str:
    return templates[instance.template_id].name


def item_description(instance: ItemInstance) -> str:
    return templates[instance.template_id].description


def items_in_room(room_id: int) -> list[ItemInstance]:
    """Scan-on-demand over `instances`. No maintained room->item index."""
    return [
        inst for inst in instances.values()
        if inst.location_kind == "room" and inst.location_id == room_id
    ]


def items_in_inventory(player_id: int) -> list[ItemInstance]:
    """Scan-on-demand over `instances`. No maintained player->item index."""
    return [
        inst for inst in instances.values()
        if inst.location_kind == "player" and inst.location_id == player_id
    ]


async def move_item(instance: ItemInstance, location_kind: str, location_id: int) -> None:
    """
    Move an item instance to a new location and write through
    immediately. Direct synchronous write, not dirty-flagged — item
    location is a rare, high-stakes, one-shot event per get/drop/give
    (a lost update means duplication or vanishing), unlike HP, which is
    high-frequency and loss-tolerant.
    """
    instance.location_kind = location_kind
    instance.location_id = location_id

    pool = get_pool()
    await pool.execute(
        "UPDATE item_instances SET location_kind = $1, location_id = $2 "
        "WHERE id = $3",
        location_kind,
        location_id,
        instance.id,
    )


def item_counts_in_room(room_id: int) -> list[tuple[ItemTemplate, int]]:
    """
    Items present in a room, grouped by template and counted for stacked
    display (e.g. "Three torches." instead of three separate lines).
    Mirrors npcs.npc_counts_in_room() exactly.
    """
    counts: dict[int, int] = {}
    order: list[int] = []

    for inst in items_in_room(room_id):
        if inst.template_id not in counts:
            counts[inst.template_id] = 0
            order.append(inst.template_id)
        counts[inst.template_id] += 1

    return [(templates[template_id], counts[template_id]) for template_id in order]


def resolve_item_in_room(raw: str, room_id: int) -> ItemInstance | None:
    """Mirrors npcs.resolve_npc_target(). Used by get/look."""
    candidates = [
        (inst.id, templates[inst.template_id].effective_keywords)
        for inst in items_in_room(room_id)
    ]
    result = targeting.resolve_target(raw, candidates)
    if not result.found:
        return None
    return instances[result.id]


def resolve_item_in_inventory(raw: str, player_id: int) -> ItemInstance | None:
    """Mirrors resolve_item_in_room(), scoped to inventory. Used by drop/give."""
    candidates = [
        (inst.id, templates[inst.template_id].effective_keywords)
        for inst in items_in_inventory(player_id)
    ]
    result = targeting.resolve_target(raw, candidates)
    if not result.found:
        return None
    return instances[result.id]


# --- Command handlers -------------------------------------------------
# Kept in this module rather than a separate commands_items.py, since
# they're thin wrappers around the state this module already owns.

from connection import Connection  # noqa: E402
from registry import registry  # noqa: E402


async def cmd_get(connection: Connection, args: str) -> None:
    from rooms import broadcast_to_room  # local import: avoids items<->rooms cycle

    raw = args.strip()
    if not raw:
        await connection.send("Get what?")
        return

    room_id = connection.player.current_room_id
    instance = resolve_item_in_room(raw, room_id)
    if instance is None:
        await connection.send("You don't see that here.")
        return

    name = item_name(instance)
    await move_item(instance, "player", connection.player.id)
    await connection.send(f"You get {name}.")
    await broadcast_to_room(
        room_id, f"{connection.player.name} gets {name}.", exclude=[connection]
    )


async def cmd_drop(connection: Connection, args: str) -> None:
    from rooms import broadcast_to_room  # local import: avoids items<->rooms cycle

    raw = args.strip()
    if not raw:
        await connection.send("Drop what?")
        return

    room_id = connection.player.current_room_id
    instance = resolve_item_in_inventory(raw, connection.player.id)
    if instance is None:
        await connection.send("You aren't carrying that.")
        return

    name = item_name(instance)
    await move_item(instance, "room", room_id)
    await connection.send(f"You drop {name}.")
    await broadcast_to_room(
        room_id, f"{connection.player.name} drops {name}.", exclude=[connection]
    )


async def cmd_give(connection: Connection, args: str) -> None:
    # Syntax: "give <player> <item>"
    recipient_name, _, item_raw = args.strip().partition(" ")
    item_raw = item_raw.strip()
    if not recipient_name or not item_raw:
        await connection.send("Give what to whom? (give <player> <item>)")
        return

    room_id = connection.player.current_room_id

    recipient_conn = next(
        (
            conn for conn in registry.connections()
            if conn.player is not None
            and conn is not connection
            and conn.player.current_room_id == room_id
            and conn.player.name.lower() == recipient_name.lower()
        ),
        None,
    )
    if recipient_conn is None:
        await connection.send("They aren't here.")
        return

    instance = resolve_item_in_inventory(item_raw, connection.player.id)
    if instance is None:
        await connection.send("You aren't carrying that.")
        return

    name = item_name(instance)
    await move_item(instance, "player", recipient_conn.player.id)
    await connection.send(f"You give {name} to {recipient_conn.player.name}.")
    await recipient_conn.send(f"{connection.player.name} gives you {name}.")


async def cmd_inventory(connection: Connection, args: str) -> None:
    held = items_in_inventory(connection.player.id)
    if not held:
        await connection.send("You aren't carrying anything.")
        return

    await connection.send("You are carrying:")
    for inst in held:
        name = item_name(inst)
        await connection.send(f"  {name[0].upper()}{name[1:]}")