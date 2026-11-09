from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.db.database import INTEGRITY_ERRORS, Connection
from app.domain.errors import (
    AuthRequiredError,
    EmailTakenError,
    InvalidCredentialsError,
    RequestInvalidError,
)
from app.domain.schemas import AuthResponse, UserOut

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_MAX = 254
PASSWORD_MIN = 8
PASSWORD_MAX = 256
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


# Hashes a password with scrypt and a random salt, returning a self-describing string.
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    enc = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${enc(salt).decode()}${enc(digest).decode()}"


# Checks a password against a stored scrypt hash in constant time.
def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Hashes a session token so the database never stores usable tokens.
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# Formats a datetime as a fixed-width UTC string so text order matches time order.
def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


# A password hash used when the email is unknown, so failed logins take the same time.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


class AuthService:
    # Stores the connection, session lifetime and an injectable clock.
    def __init__(
        self,
        conn: Connection,
        session_days: int,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._conn = conn
        self._session_days = session_days
        self._now = now

    # Normalises the email and checks both fields, raising a validation error on problems.
    @staticmethod
    def _clean(email: str, password: str) -> str:
        email = email.strip().lower()
        problems = []
        if not EMAIL_RE.match(email) or len(email) > EMAIL_MAX:
            problems.append({"field": "email", "reason": "Enter a valid email address."})
        if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
            problems.append(
                {"field": "password", "reason": f"Use at least {PASSWORD_MIN} characters."}
            )
        if problems:
            raise RequestInvalidError(problems[0]["reason"], details=problems)
        return email

    # Creates a session row for the user and returns the token with the user.
    def _start_session(self, user_id: str, email: str, created_at: str) -> AuthResponse:
        token = secrets.token_urlsafe(32)
        now = self._now()
        self._conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at)"
            " VALUES (?, ?, ?, ?)",
            (
                _token_hash(token),
                user_id,
                _iso(now),
                _iso(now + timedelta(days=self._session_days)),
            ),
        )
        self._conn.commit()
        user = UserOut(id=user_id, email=email, created_at=datetime.fromisoformat(created_at))
        return AuthResponse(token=token, user=user)

    # Registers a new account and logs it in.
    def register(self, email: str, password: str) -> AuthResponse:
        email = self._clean(email, password)
        user_id = str(uuid.uuid4())
        created_at = _iso(self._now())
        try:
            self._conn.execute(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, email, hash_password(password), created_at),
            )
        except INTEGRITY_ERRORS:
            raise EmailTakenError() from None
        return self._start_session(user_id, email, created_at)

    # Checks the email and password and starts a session, or raises invalid credentials.
    def login(self, email: str, password: str) -> AuthResponse:
        email = email.strip().lower()
        row = self._conn.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = ?", (email,)
        ).fetchone()
        ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
        if row is None or not ok:
            raise InvalidCredentialsError()
        return self._start_session(row["id"], row["email"], row["created_at"])

    # Returns the user that owns a live session token, or raises auth required.
    def user_for_token(self, token: str) -> UserOut:
        row = self._conn.execute(
            """
            SELECT u.id, u.email, u.created_at, s.expires_at FROM sessions s
            JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?
            """,
            (_token_hash(token),),
        ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= self._now():
            raise AuthRequiredError()
        return UserOut(
            id=row["id"], email=row["email"], created_at=datetime.fromisoformat(row["created_at"])
        )

    # Ends one session so its token stops working.
    def logout(self, token: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        self._conn.commit()
