"""
security/auth.py
==================
Authentication layer — JWT tokens + bcrypt password hashing.

Functions
---------
create_user      — register a new user with a hashed password
login            — verify credentials and return a signed JWT
verify_token     — decode and validate a JWT (use in FastAPI dependencies)
change_password  — re-hash and update password
deactivate_user  — soft-disable a user without deleting

Exception
---------
AuthError — raised for all auth / authorisation failures

Environment variables
---------------------
JWT_SECRET      : long random string — KEEP SECRET
JWT_EXPIRES_MIN : token lifetime in minutes (default 60)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

from db.models import User

load_dotenv()

JWT_SECRET      = os.getenv("JWT_SECRET")
JWT_ALGORITHM   = "HS256"
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "60"))

if not JWT_SECRET:
    raise EnvironmentError(
        "[Auth] JWT_SECRET is not set in .env — add a long random string."
    )


class AuthError(Exception):
    """Raised for all authentication / authorisation failures."""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _issue_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":          user.id,
        "name":         user.name,
        "role":         user.role,
        "is_sys_admin": user.is_sys_admin,
        "iat":          now,
        "exp":          now + timedelta(minutes=JWT_EXPIRES_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── Public API ────────────────────────────────────────────────────────────────

async def create_user(
    email: str,
    name: str,
    password: str,
    role: str,
    is_sys_admin: bool = False,
) -> dict:
    """
    Register a new user with a bcrypt-hashed password.

    Raises ValueError for invalid input, AuthError if email already exists.
    """
    email = email.strip().lower()
    role  = role.strip().upper()

    if not email or "@" not in email:
        raise ValueError("A valid email is required.")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    if await User.get(email):
        raise AuthError(f"Email '{email}' is already registered.")

    user = User(
        id              = email,
        email           = email,
        name            = name.strip(),
        role            = role,
        is_sys_admin    = is_sys_admin,
        hashed_password = _hash_password(password),
        created_at      = datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        active          = True,
    )
    await user.insert()
    return user.to_dict()


async def login(email: str, password: str) -> dict:
    """
    Verify credentials and return a signed JWT on success.

    Returns { token, expires_in, user }.
    Raises AuthError for wrong credentials or inactive accounts.
    """
    email = email.strip().lower()
    user  = await User.get(email)

    if not user:
        raise AuthError("Invalid email or password.")
    if not user.active:
        raise AuthError("This account has been deactivated.")
    if not _verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password.")

    user.last_login = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await user.save()

    return {
        "token":      _issue_token(user),
        "expires_in": JWT_EXPIRES_MIN * 60,
        "user":       user.to_dict(),
    }


def verify_token(token: str) -> dict:
    """
    Decode and validate a JWT.  Use as a FastAPI dependency.

    Returns the decoded payload: { sub, name, role, is_sys_admin, iat, exp }.
    Raises AuthError for expired or invalid tokens.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired. Please log in again.")
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}")


async def change_password(email: str, old_password: str, new_password: str) -> None:
    """Re-hash and save a new password after verifying the old one."""
    if not new_password or len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters.")

    email = email.strip().lower()
    user  = await User.get(email)
    if not user:
        raise AuthError("User not found.")
    if not _verify_password(old_password, user.hashed_password):
        raise AuthError("Old password is incorrect.")

    user.hashed_password = _hash_password(new_password)
    await user.save()


async def deactivate_user(email: str) -> None:
    """Soft-disable a user (active=False).  Preserves all data and assignments."""
    email = email.strip().lower()
    user  = await User.get(email)
    if not user:
        raise AuthError(f"User '{email}' not found.")
    user.active = False
    await user.save()
