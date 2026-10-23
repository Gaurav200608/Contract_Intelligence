import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Iterator, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = ROOT_DIR / "backend" / "auth_data" / "accounts.sqlite3"
SESSION_COOKIE = "ci_session"
CSRF_COOKIE = "ci_csrf"
SESSION_SECONDS = 12 * 60 * 60
REMEMBER_SECONDS = 30 * 24 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 8
PASSWORD_HASHER = PasswordHasher()
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    email: str
    role: str
    csrf_token: str
    expires_at: int
    session_token: Optional[str] = None


def database_path() -> Path:
    configured = os.environ.get("AUTH_DATABASE_PATH")
    path = Path(configured).expanduser() if configured else DEFAULT_DATABASE
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                csrf_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                persistent INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_login_attempts (
                attempt_key TEXT PRIMARY KEY,
                failures INTEGER NOT NULL,
                window_started INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions(expires_at)"
        )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _attempt_key(kind: str, value: str) -> str:
    normalized = value.strip().casefold()
    return hashlib.sha256(f"{kind}:{normalized}".encode("utf-8")).hexdigest()


def _rate_limited(connection: sqlite3.Connection, keys: list[str], now: int) -> bool:
    for key in keys:
        row = connection.execute(
            "SELECT failures, window_started, locked_until "
            "FROM auth_login_attempts WHERE attempt_key = ?",
            (key,),
        ).fetchone()
        if row and (
            row["locked_until"] > now
            or (
                row["window_started"] > now - LOGIN_WINDOW_SECONDS
                and row["failures"] >= LOGIN_MAX_FAILURES
            )
        ):
            return True
    return False


def _record_failure(connection: sqlite3.Connection, keys: list[str], now: int) -> None:
    for key in keys:
        row = connection.execute(
            "SELECT failures, window_started FROM auth_login_attempts "
            "WHERE attempt_key = ?",
            (key,),
        ).fetchone()
        if not row or row["window_started"] <= now - LOGIN_WINDOW_SECONDS:
            failures = 1
            window_started = now
        else:
            failures = row["failures"] + 1
            window_started = row["window_started"]
        locked_until = now + LOGIN_WINDOW_SECONDS if failures >= LOGIN_MAX_FAILURES else 0
        connection.execute(
            """
            INSERT INTO auth_login_attempts
                (attempt_key, failures, window_started, locked_until)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(attempt_key) DO UPDATE SET
                failures = excluded.failures,
                window_started = excluded.window_started,
                locked_until = excluded.locked_until
            """,
            (key, failures, window_started, locked_until),
        )


def _clear_failures(connection: sqlite3.Connection, keys: list[str]) -> None:
    connection.executemany(
        "DELETE FROM auth_login_attempts WHERE attempt_key = ?",
        ((key,) for key in keys),
    )


def authenticate(
    login: str, password: str, remember_me: bool, client_ip: str
) -> tuple[Optional[AuthenticatedUser], bool]:
    initialize_database()
    now = int(time.time())
    normalized_login = login.strip()
    keys = [
        _attempt_key("ip", client_ip),
        _attempt_key("login", normalized_login),
    ]
    with connect() as connection:
        connection.execute(
            "DELETE FROM auth_login_attempts WHERE window_started <= ? AND locked_until <= ?",
            (now - LOGIN_WINDOW_SECONDS, now),
        )
        if _rate_limited(connection, keys, now):
            return None, True

        user = connection.execute(
            """
            SELECT id, username, email, password_hash, role
            FROM auth_users
            WHERE (username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE)
              AND is_active = 1
            """,
            (normalized_login, normalized_login),
        ).fetchone()

        password_valid = False
        if user:
            try:
                password_valid = PASSWORD_HASHER.verify(user["password_hash"], password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                password_valid = False
        else:
            try:
                PASSWORD_HASHER.verify(DUMMY_PASSWORD_HASH, password)
            except VerifyMismatchError:
                pass

        if not user or not password_valid:
            _record_failure(connection, keys, now)
            return None, False

        if PASSWORD_HASHER.check_needs_rehash(user["password_hash"]):
            connection.execute(
                "UPDATE auth_users SET password_hash = ? WHERE id = ?",
                (PASSWORD_HASHER.hash(password), user["id"]),
            )

        _clear_failures(connection, keys)
        duration = REMEMBER_SECONDS if remember_me else SESSION_SECONDS
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        connection.execute(
            """
            INSERT INTO auth_sessions
                (token_hash, user_id, csrf_hash, expires_at, persistent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _token_hash(session_token),
                user["id"],
                _token_hash(csrf_token),
                now + duration,
                int(remember_me),
                now,
            ),
        )
        authenticated = AuthenticatedUser(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            role=user["role"],
            csrf_token=csrf_token,
            expires_at=now + duration,
            session_token=session_token,
        )
        return authenticated, False


def get_session(token: Optional[str]) -> Optional[AuthenticatedUser]:
    if not token or len(token) > 256:
        return None
    initialize_database()
    now = int(time.time())
    with connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
        row = connection.execute(
            """
            SELECT u.id, u.username, u.email, u.role, s.csrf_hash, s.expires_at
            FROM auth_sessions s
            JOIN auth_users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1
            """,
            (_token_hash(token), now),
        ).fetchone()
        if not row:
            return None
        return AuthenticatedUser(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            role=row["role"],
            csrf_token=row["csrf_hash"],
            expires_at=row["expires_at"],
        )


def ensure_csrf_token(
    session_token: Optional[str], session: AuthenticatedUser, cookie_token: str
) -> str:
    if cookie_token and hmac.compare_digest(
        _token_hash(cookie_token), session.csrf_token
    ):
        return cookie_token
    token = secrets.token_urlsafe(32)
    initialize_database()
    with connect() as connection:
        connection.execute(
            "UPDATE auth_sessions SET csrf_hash = ? WHERE token_hash = ?",
            (_token_hash(token), _token_hash(session_token or "")),
        )
    return token


def csrf_valid(session: Optional[AuthenticatedUser], cookie_token: str, header_token: str) -> bool:
    if not cookie_token or not header_token:
        return False
    if not hmac.compare_digest(cookie_token, header_token):
        return False
    if session:
        return hmac.compare_digest(_token_hash(cookie_token), session.csrf_token)
    return True


def revoke_session(token: Optional[str]) -> None:
    if not token:
        return
    initialize_database()
    with connect() as connection:
        connection.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),)
        )


def create_admin(username: str, email: str, password: str) -> None:
    normalized_username = username.strip()
    normalized_email = email.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", normalized_username):
        raise ValueError("Username must be 3-64 letters, numbers, dots, underscores, or hyphens.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        raise ValueError("Enter a valid email address.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

    initialize_database()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO auth_users (username, email, password_hash, role, created_at)
            VALUES (?, ?, ?, 'admin', ?)
            """,
            (
                normalized_username,
                normalized_email,
                PASSWORD_HASHER.hash(password),
                int(time.time()),
            ),
        )


def _create_admin_interactively() -> None:
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass("Admin password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    create_admin(username, email, password)
    print(f"Administrator '{username}' created in {database_path()}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "create-admin":
        raise SystemExit("Usage: python -m backend.auth create-admin")
    try:
        _create_admin_interactively()
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise SystemExit(str(exc)) from exc
