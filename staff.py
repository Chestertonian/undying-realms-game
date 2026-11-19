"""
Staff gating and staff commands. The is_staff flag is set via SQL only.
"""

from __future__ import annotations

import logging
from functools import wraps

import db
from command_types import CommandHandler
from connection import Connection
from guilds import in_guild
from registry import registry
from roles import ROLES, find_role

log = logging.getLogger(__name__)


def staff_only(handler: CommandHandler) -> CommandHandler:
    @wraps(handler)
    async def wrapper(connection: Connection, args: str) -> None:
        if connection.player is None or not connection.player.is_staff:
            log.warning(
                "staff_only: player=%r is_staff=%r",
                connection.player.name if connection.player else None,
                connection.player.is_staff if connection.player else None,
            )
            await connection.send("Unknown command.")
            return
        await handler(connection, args)

    return wrapper


def _find_online(name: str) -> Connection | None:
    return next(
        (
            conn
            for conn in registry.connections()
            if conn.player is not None and conn.player.name.lower() == name.lower()
        ),
        None,
    )


def _parse(args: str) -> tuple[str, str]:
    name, _, role_raw = args.strip().partition(" ")
    return name, role_raw.strip()


@staff_only
async def cmd_grant(connection: Connection, args: str) -> None:
    target_name, role_raw = _parse(args)
    if not target_name or not role_raw:
        await connection.send("Grant what to whom? (grant <player> <role>)")
        return

    role = find_role(role_raw)
    if role is None:
        valid = ", ".join(r.name for r in ROLES.values())
        await connection.send(f"Unknown role. Valid roles: {valid}")
        return

    target_conn = _find_online(target_name)
    if target_conn is None:
        await connection.send("No such player is online.")
        return
    target = target_conn.player

    if role.key in target.roles:
        await connection.send(f"{target.name} already has the {role.name} role.")
        return

    if role.guild_name is not None and not in_guild(target, role.guild_name):
        await connection.send(
            f"{target.name} must be a member of the {role.guild_name} to hold that role."
        )
        return

    result = await db.get_pool().execute(
        "INSERT INTO player_roles (player_id, role) VALUES ($1, $2) "
        "ON CONFLICT DO NOTHING",
        target.id,
        role.key,
    )
    if result != "INSERT 0 1":
        await connection.send(f"{target.name} already has the {role.name} role.")
        return

    target.roles.add(role.key)
    log.info(
        "staff %s (id %d) granted role %s to %s (id %d)",
        connection.player.name,
        connection.player.id,
        role.key,
        target.name,
        target.id,
    )
    await connection.send(f"You grant the {role.name} role to {target.name}.")
    await registry.broadcast_to_all(f"   << {target.name} is now the {role.name}. >>")
    await target_conn.send(f"You have been granted the {role.name} role.")


@staff_only
async def cmd_revoke(connection: Connection, args: str) -> None:
    target_name, role_raw = _parse(args)
    if not target_name or not role_raw:
        await connection.send("Revoke what from whom? (revoke <player> <role>)")
        return

    role = find_role(role_raw)
    if role is None:
        valid = ", ".join(r.name for r in ROLES.values())
        await connection.send(f"Unknown role. Valid roles: {valid}")
        return

    target_conn = _find_online(target_name)
    if target_conn is None:
        await connection.send("No such player is online.")
        return
    target = target_conn.player

    result = await db.get_pool().execute(
        "DELETE FROM player_roles WHERE player_id = $1 AND role = $2",
        target.id,
        role.key,
    )
    if result != "DELETE 1":
        await connection.send(f"{target.name} doesn't have the {role.name} role.")
        return

    target.roles.discard(role.key)
    log.info(
        "staff %s (id %d) revoked role %s from %s (id %d)",
        connection.player.name,
        connection.player.id,
        role.key,
        target.name,
        target.id,
    )
    await connection.send(f"You revoke the {role.name} role from {target.name}.")
    await target_conn.send(f"Your {role.name} role has been revoked.")
