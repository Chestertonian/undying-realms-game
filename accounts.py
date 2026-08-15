"""
Account model and authentication.

Password hashing/verification is CPU-bound and synchronous (bcrypt has no
async API), so it's pushed onto the default thread pool via
run_in_executor rather than called directly — otherwise every login
attempt would stall the event loop, freezing every other player's
connection for the duration of the hash.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

import asyncpg
import bcrypt

import db

BCRYPT_ROUNDS = 12


@dataclass
class Account:
    id: int
    username: str
    email: str | None
    password_hash: str
    created_at: datetime
    last_login: datetime | None


async def account_exists(username: str) -> bool:
    pool = db.get_pool()
    row = await pool.fetchval(
        "SELECT 1 FROM accounts WHERE username = $1", username
    )
    return row is not None


async def load_account(username: str) -> Account | None:
    pool = db.get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, email, password_hash, created_at, last_login "
        "FROM accounts WHERE username = $1",
        username,
    )
    if row is None:
        return None
    return Account(**dict(row))


async def verify_password(username: str, password: str) -> bool:
    account = await load_account(username)
    if account is None:
        return False

    loop = asyncio.get_running_loop()
    is_valid = await loop.run_in_executor(
        None,
        bcrypt.checkpw,
        password.encode("utf-8"),
        account.password_hash.encode("utf-8"),
    )

    if is_valid:
        await _touch_last_login(account.id)

    return is_valid


async def create_account(
    username: str, password: str, email: str | None = None
) -> Account:
    password_hash = await _hash_password(password)

    pool = db.get_pool()
    try:
        row = await pool.fetchrow(
            "INSERT INTO accounts (username, email, password_hash) "
            "VALUES ($1, $2, $3) "
            "RETURNING id, username, email, password_hash, created_at, last_login",
            username,
            email,
            password_hash,
        )
    except asyncpg.UniqueViolationError as exc:
        # username or email already taken; caller (LoginHandler) is
        # expected to have already checked account_exists() for username,
        # so this is mainly a safety net against races and bad email input.
        raise ValueError(f"Account creation failed: {exc}") from exc

    return Account(**dict(row))


async def _hash_password(password: str) -> str:
    loop = asyncio.get_running_loop()
    hashed = await loop.run_in_executor(
        None,
        lambda: bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)),
    )
    return hashed.decode("utf-8")


async def _touch_last_login(account_id: int) -> None:
    pool = db.get_pool()
    await pool.execute(
        "UPDATE accounts SET last_login = now() WHERE id = $1", account_id
    )