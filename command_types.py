# command_types.py
from __future__ import annotations
from typing import Awaitable, Callable
from connection import Connection

CommandHandler = Callable[[Connection, str], Awaitable[None]]