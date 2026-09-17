"""Local authentication for the Digital Oilfield Monitoring System.

Uses SQLite for user records and PBKDF2-HMAC-SHA256 password hashing.
No plaintext passwords are stored.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timezone

import config

AUTH_DB_PATH = config.DB_PATH
HASH_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 310_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 8
VALID_ROLES = {"admin", "operator", "viewer"}


def _connect():
    os.makedirs(os.path.dirname(AUTH_DB_PATH) or ".", exist_ok=True)
    return sqlite3.connect(AUTH_DB_PATH)


def init_auth_db() -> None:
    """Create authentication tables if they do not already exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'operator',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                event TEXT NOT NULL,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return digest.hex()


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must contain at least {MIN_PASSWORD_LENGTH} characters."
    return True, ""


def create_user(username: str, password: str, role: str = "operator") -> None:
    """Create a local user with a salted password hash."""
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if role not in VALID_ROLES:
        raise ValueError("Invalid user role.")
    valid, message = validate_password(password)
    if not valid:
        raise ValueError(message)

    init_auth_db()
    salt = secrets.token_bytes(SALT_BYTES)
    password_hash = _hash_password(password, salt)
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, salt, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, password_hash, salt.hex(), role, created_at),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("That username already exists.") from exc


def user_count() -> int:
    init_auth_db()
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def authenticate(username: str, password: str):
    """Return user information on success, otherwise None."""
    init_auth_db()
    username = username.strip()
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash, salt, role, is_active
            FROM users WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if not row or not row[5]:
            _record_event(conn, username, "login", False, now)
            return None

        expected = row[2]
        actual = _hash_password(password, bytes.fromhex(row[3]))
        if not hmac.compare_digest(expected, actual):
            _record_event(conn, username, "login", False, now)
            return None

        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row[0]))
        _record_event(conn, username, "login", True, now)
        conn.commit()

    return {"id": row[0], "username": row[1], "role": row[4]}


def _record_event(conn, username: str, event: str, success: bool, created_at: str):
    conn.execute(
        "INSERT INTO auth_events (username, event, success, created_at) VALUES (?, ?, ?, ?)",
        (username, event, int(success), created_at),
    )
