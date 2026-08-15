-- schema.sql

CREATE TABLE accounts (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login    TIMESTAMPTZ
);

CREATE TABLE players (
    id            SERIAL PRIMARY KEY,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    name          TEXT UNIQUE NOT NULL,
    race          TEXT NOT NULL,
    background    TEXT NOT NULL,
    stats         JSONB NOT NULL,
    room_id       INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);