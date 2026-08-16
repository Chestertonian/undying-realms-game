"""
Login/character-selection state machine.

Owns a Connection from initial welcome through to a ready-to-play Player.
Knows nothing about telnet/sockets (Connection's job) or the game loop/
rooms/combat (caller's job) — its only output is a Player or None.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Awaitable, Callable, Optional

from connection import Connection

from accounts import *
from player import load_characters_for_account
from registry import registry

class LoginState(Enum):
    USERNAME = auto()
    PASSWORD = auto()
    NEW_ACCOUNT_CONFIRM = auto()
    NEW_ACCOUNT_PASSWORD = auto()
    CHARACTER_MENU = auto()
    CHARACTER_CREATE = auto()
    DONE = auto()


class LoginHandler:
    """Drives one connection through login and character selection."""

    def __init__(self, conn: Connection):
        self.conn = conn
        self.state = LoginState.USERNAME
        self.account = None  # type: ignore[assignment]  # Account, once accounts.py exists
        self.pending_username: Optional[str] = None
        self.selected_player = None  # type: ignore[assignment]  # Player

        self._state_handlers: dict[LoginState, Callable[[], Awaitable[object]]] = {
            LoginState.USERNAME: self._handle_username,
            LoginState.PASSWORD: self._handle_password,
            LoginState.NEW_ACCOUNT_CONFIRM: self._handle_new_account_confirm,
            LoginState.NEW_ACCOUNT_PASSWORD: self._handle_new_account_password,
            LoginState.CHARACTER_MENU: self._handle_character_menu,
            LoginState.CHARACTER_CREATE: self._handle_character_create,
        }

    async def run(self):
        """
        Drive the state machine to completion.

        Returns a ready-to-play Player, or None if the connection dropped
        before login/character selection finished.
        """
        await self.conn.send("Welcome to Undying Realms.")

        while self.state != LoginState.DONE:
            handler = self._state_handlers[self.state]
            result = await handler()
            if result is None:
                return None

        return self.selected_player

    # --- per-state handlers ---
    # Each returns None (connection dead, abort) or truthy (continue looping).
    # Handlers advance self.state themselves; returning without changing
    # self.state means "reprompt the same state".

    async def _handle_username(self):
        await self.conn.send("Username:")
        raw = await self.conn.receive_line()
        if raw is None:
            return None

        name = raw.strip()
        if not _valid_username_format(name):
            await self.conn.send("Invalid username. Letters, numbers, 3-20 characters.")
            return True  # reprompt USERNAME

        self.pending_username = name
        if await account_exists(name):
            self.state = LoginState.PASSWORD
        else:
            self.state = LoginState.NEW_ACCOUNT_CONFIRM
        return True

    async def _handle_password(self):
        await self.conn.send("Password:")
        await self.conn.request_password_mode(masked=True)
        raw = await self.conn.receive_line()
        await self.conn.request_password_mode(masked=False)
        if raw is None:
            return None

        if not await verify_password(self.pending_username, raw):
            await self.conn.send("Incorrect password.")
            self.state = LoginState.USERNAME  # back to start; attempt-limit TBD
            return True

        self.account = await load_account(self.pending_username)
        self.state = LoginState.CHARACTER_MENU
        return True
    
    
    async def _handle_new_account_confirm(self):
        await self.conn.send(f"No account '{self.pending_username}'. Create it? (y/n)")
        raw = await self.conn.receive_line()
        if raw is None:
            return None

        if raw.strip().lower().startswith("y"):
            self.state = LoginState.NEW_ACCOUNT_PASSWORD
        else:
            self.state = LoginState.USERNAME
        return True

    async def _handle_new_account_password(self):
        await self.conn.send("Choose a password:")
        await self.conn.request_password_mode(masked=True)
        pw1 = await self.conn.receive_line()
        await self.conn.send("Confirm password:")
        pw2 = await self.conn.receive_line()
        await self.conn.request_password_mode(masked=False)
        if pw1 is None or pw2 is None:
            return None

        if pw1 != pw2:
            await self.conn.send("Passwords did not match.")
            return True  # reprompt NEW_ACCOUNT_PASSWORD

        self.account = await create_account(self.pending_username, pw1)
        self.state = LoginState.CHARACTER_MENU
        return True

    async def _handle_character_menu(self):
        characters = await load_characters_for_account(self.account.id)

        await self.conn.send("--- Characters ---")
        for i, ch in enumerate(characters, start=1):
            await self.conn.send(f"[{i}] {ch.name}")
        await self.conn.send("[N] Create new character")

        raw = await self.conn.receive_line()
        if raw is None:
            return None
        choice = raw.strip().lower()

        if choice == "n":
            self.state = LoginState.CHARACTER_CREATE
            return True

        try:
            index = int(choice) - 1
            player = characters[index]
        except (ValueError, IndexError):
            await self.conn.send("Invalid selection.")
            return True  # reprompt CHARACTER_MENU

        if registry.is_online(player.id):
            await self.conn.send("That character is already connected. Disconnect it? (y/n)")
            raw = await self.conn.receive_line()
            if raw is None:
                return None
            if raw.strip().lower().startswith("y"):
                await registry.kick(player.id)
            else:
                return True  # reprompt CHARACTER_MENU

        self.selected_player = player
        self.state = LoginState.DONE
        return True

    async def _handle_character_create(self):
        from character_creation import CharacterCreationHandler  # local import avoids a cycle

        self.selected_player = await CharacterCreationHandler(self.conn).run(self.account.id)
        self.state = LoginState.DONE
        return True


def _valid_username_format(name: str) -> bool:
    return 3 <= len(name) <= 20 and name.isalpha()