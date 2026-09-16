"""
Basic combat: unarmed only, no item dependency.

Combat state is tracked as a set of directed "engagement" edges rather
than a bounded Fight object, so multi-target and third-party joining
fall out of the model naturally instead of needing special-case logic.

  engaged_with[attacker] -> set of everyone attacker has ever targeted
                             in the current fight(s). Only grows; cleared
                             wholesale on flee/death/respawn. NEVER has
                             members removed individually (NPCs "remember"
                             a fled target if they return to the room).

  current_target[attacker] -> single pointer into engaged_with[attacker],
                               the one actually struck each tick. May
                               point at an entity no longer in the room
                               (see reassignment pass below).

Both dicts are module-level, mirroring db.py's _pool pattern.

Players are NOT held in a module-level dict — Player objects live on
Connection objects (registry.py), so resolving a ("player", id) EntityRef
back to a live Player means scanning registry.connections(). A player
with no live connection (disconnected) resolves to None, which is also
how the tick loop treats a disconnected player as absent without a
separate disconnect hook.
"""

from __future__ import annotations

import asyncio
import random
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from player import Player
    from npcs import NpcInstance

EntityRef = tuple[Literal["player", "npc"], int]

engaged_with: dict[EntityRef, set[EntityRef]] = {}
current_target: dict[EntityRef, EntityRef] = {}

TICK_SECONDS = 2.0
UNARMED_DIE = 8


# ---------------------------------------------------------------------------
# Entity resolution — bridges EntityRef back to the real Player/NpcInstance
# ---------------------------------------------------------------------------

def _resolve_player(player_id: int) -> "Player | None":
    """Scans live connections for a matching player id. Returns None if
    the player has no live connection (disconnected) — this is also the
    mechanism by which the tick loop treats a disconnected player as
    absent, with no separate disconnect hook required in this module."""
    from registry import connections

    for conn in connections():
        if conn.player is not None and conn.player.id == player_id:
            return conn.player
    return None


def _resolve(ref: EntityRef) -> "Player | NpcInstance | None":
    kind, id_ = ref
    if kind == "player":
        return _resolve_player(id_)
    else:
        from npcs import instances
        return instances.get(id_)


def _room_id(ref: EntityRef) -> int | None:
    entity = _resolve(ref)
    if entity is None:
        return None
    return entity.current_room_id if ref[0] == "player" else entity.room_id


def _same_room(a: EntityRef, b: EntityRef) -> bool:
    room_a, room_b = _room_id(a), _room_id(b)
    return room_a is not None and room_a == room_b


def _current_hp(ref: EntityRef) -> int | None:
    entity = _resolve(ref)
    return None if entity is None else entity.current_hp


def _display_name(ref: EntityRef) -> str:
    entity = _resolve(ref)
    if entity is None:
        return "someone"
    if ref[0] == "player":
        return entity.name
    from npcs import templates
    return templates[entity.template_id].name


def _adjust_hp(ref: EntityRef, delta: int) -> None:
    """Dispatches to the right mutator based on entity kind. Both sides
    clamp-and-dirty-flag internally."""
    entity = _resolve(ref)
    if entity is None:
        return  # target vanished (e.g. disconnected) between snapshot and resolution
    if ref[0] == "player":
        from player import adjust_current_hp as adjust_player_hp
        adjust_player_hp(entity, delta)
    else:
        from npcs import adjust_current_hp as adjust_npc_hp
        adjust_npc_hp(entity, delta)


# ---------------------------------------------------------------------------
# Combined target resolution (NPCs + players in a room)
# ---------------------------------------------------------------------------

def resolve_combat_target(raw: str, room_id: int) -> EntityRef | None:
    """
    Resolves a raw target string against every NPC and player in a room.
    NPCs are checked first, then players, in candidate order passed to
    targeting.resolve_target — this only matters for ordinal numbering
    if a keyword collides across kinds, which should be rare in practice.

    NPC instance ids and player ids are separate Postgres serial columns
    on separate tables, so no value-collision risk between the two id
    spaces; the post-hoc "which pool did this id come from" check below
    is safe on that basis.
    """
    from targeting import resolve_target
    from npcs import npcs_in_room, templates as npc_templates
    from rooms import players_in_room

    npc_candidates = [
        (inst.id, npc_templates[inst.template_id].effective_keywords)
        for inst in npcs_in_room(room_id)
    ]
    player_candidates = [
        (player.id, [player.name.lower()])
        for player in players_in_room(room_id)
    ]

    result = resolve_target(raw, npc_candidates + player_candidates)
    if not result.found:
        return None

    npc_ids = {cand_id for cand_id, _ in npc_candidates}
    if result.id in npc_ids:
        return ("npc", result.id)
    return ("player", result.id)


# ---------------------------------------------------------------------------
# Engagement mutators
# ---------------------------------------------------------------------------

def _ensure_engaged(attacker: EntityRef, target: EntityRef) -> None:
    engaged_with.setdefault(attacker, set()).add(target)


def engage(attacker: EntityRef, target: EntityRef) -> None:
    """Used by kill/target commands, and by auto-aggro on taking damage.
    Adds target to engaged_with if absent, and always sets current_target
    to it — 'pick within / append to the set' semantics."""
    _ensure_engaged(attacker, target)
    current_target[attacker] = target


def disengage_self(entity: EntityRef) -> None:
    """Used by flee, death, respawn, and disconnect cleanup. Clears the
    entity's own outgoing state only — does NOT remove entity from
    others' engaged_with sets (NPCs 'remember')."""
    engaged_with.pop(entity, None)
    current_target.pop(entity, None)


def is_in_combat(entity: EntityRef) -> bool:
    return bool(engaged_with.get(entity))


def _clear_as_target(dead: EntityRef) -> None:
    """On death: remove `dead` from every attacker's engaged_with set,
    and unset current_target wherever it pointed at `dead`."""
    for targets in engaged_with.values():
        targets.discard(dead)
    for attacker, tgt in list(current_target.items()):
        if tgt == dead:
            del current_target[attacker]


# ---------------------------------------------------------------------------
# Command-facing entry points
# ---------------------------------------------------------------------------

def cmd_kill(actor: EntityRef, keyword: str, room_id: int) -> str:
    target = resolve_combat_target(keyword, room_id)
    if target is None:
        return "You don't see that here."
    if target == actor:
        return "You can't attack yourself."

    engage(actor, target)
    return f"You attack {_display_name(target)}!"


def cmd_target(actor: EntityRef, keyword: str, room_id: int) -> str:
    return cmd_kill(actor, keyword, room_id)


def cmd_flee(actor: EntityRef, room_id: int) -> str:
    """Takes room_id, not a Room object, for consistency with
    cmd_kill/cmd_target — combat.py's command entry points all take bare
    ids, and look up whatever richer object they need internally."""
    if not is_in_combat(actor):
        return "You aren't fighting anyone."

    from movement import get_exits, move_entity
    from rooms import rooms

    room = rooms[room_id]
    exits = get_exits(room)
    if not exits:
        return "There's nowhere to flee to!"

    direction, destination = random.choice(list(exits.items()))
    disengage_self(actor)
    move_entity(actor, destination)
    return f"You flee {direction}!"


def blocks_move(actor: EntityRef) -> bool:
    return is_in_combat(actor)


def on_player_disconnect(player_id: int) -> None:
    """Call from the connection-close/logout path (wherever
    Connection.player currently gets cleared) so a disconnected player's
    edges don't linger pointing at a Player object that no longer
    resolves. Clears the player's own outgoing state only — matches
    flee/death semantics: others' engaged_with sets still 'remember'
    them, same as a fled target does."""
    disengage_self(("player", player_id))


# ---------------------------------------------------------------------------
# Tick resolution
# ---------------------------------------------------------------------------

async def combat_tick_loop() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        await _resolve_tick()


async def _resolve_tick() -> None:
    """Async so death handling can await its DB writes inline rather than
    fire-and-forget — a dead NPC's DELETE and a respawned player's UPDATE
    complete (or the whole tick raises) before the tick is considered
    done, closing the crash window where in-memory state and the DB could
    disagree. Costs a brief pause on death events only; deaths aren't
    happening every tick, and a local Postgres write is fast."""
    # 1. Snapshot current_target at tick start — one pass, no mid-tick mutation.
    snapshot = list(current_target.items())
    dead: set[EntityRef] = set()

    # 2. Damage pass, with auto-aggro on first hit.
    for attacker, target in snapshot:
        if attacker in dead or target in dead:
            continue
        if not _same_room(attacker, target):
            continue  # silent whiff; reassignment pass handles retargeting

        if attacker not in engaged_with.get(target, ()):
            engage(target, attacker)

        roll = random.randint(1, UNARMED_DIE)
        _adjust_hp(target, -roll)

        hp = _current_hp(target)
        if hp is not None and hp <= 0:
            dead.add(target)

    # 3. Death pass — after full damage pass, using post-damage HP.
    for entity in dead:
        _clear_as_target(entity)
        disengage_self(entity)
        if entity[0] == "npc":
            await _delete_npc_instance(entity)
        else:
            await _respawn_player(entity)

    # 4. Reassignment pass — absent current_target with a present alternative.
    for attacker, target in list(current_target.items()):
        if attacker in dead or target in dead:
            continue
        if _same_room(attacker, target):
            continue

        alt = _find_present_alternative(attacker, exclude=target)
        if alt is not None:
            current_target[attacker] = alt
        # else: leave current_target pointed at the absent target — resumes
        # automatically once attacker/target share a room again.


def _find_present_alternative(attacker: EntityRef, exclude: EntityRef) -> EntityRef | None:
    for candidate in engaged_with.get(attacker, ()):
        if candidate != exclude and _same_room(attacker, candidate):
            return candidate
    return None


async def _delete_npc_instance(ref: EntityRef) -> None:
    """One-shot event — direct synchronous (awaited-inline) delete, not
    dirty-flagged. Awaited by _resolve_tick() so the DB write completes
    within the same tick as the in-memory removal."""
    from npcs import instances
    from db import get_pool

    instances.pop(ref[1], None)

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM npc_instances WHERE id = $1", ref[1])


async def _respawn_player(ref: EntityRef) -> None:
    """One-shot event — direct synchronous (awaited-inline) write, not
    dirty-flagged. Always writes the DB row (so a disconnected-mid-fight
    player is correct on next login), and additionally updates the
    in-memory Player object if a live connection still exists."""
    from db import get_pool

    player_id = ref[1]
    player = _resolve_player(player_id)

    if player is not None:
        player.current_hp = player.max_hp
        player.current_sp = player.max_sp
        player.current_ep = player.max_ep
        player.current_room_id = 1

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE players
            SET current_hp = max_hp,
                current_sp = max_sp,
                current_ep = max_ep,
                current_room_id = 1
            WHERE id = $1
            """,
            player_id,
        )