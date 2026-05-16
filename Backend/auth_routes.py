"""
Agent authentication routes.

Passwords are NEVER stored or compared in plaintext anywhere in our codebase.
We rely on Supabase Auth, which:
  * On signup, bcrypt-hashes the password and stores it in
    `auth.users.encrypted_password`.
  * On login, takes the plaintext password the agent submits, hashes it with
    the same bcrypt parameters, and compares it against the stored hash.
    Only if the hashes match does Supabase return a session.

This module is just a thin wrapper around that flow. The frontend only ever
receives a JWT access_token + refresh_token, never a password or a hash.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, field_validator

from supabase_client import supabase

router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


class AuthBody(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or len(email) < 5:
            raise ValueError("Invalid email address")
        return email

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value is None or len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
            )
        return value


def _session_payload(session, user):
    """Shape the response sent back to the frontend. Never includes the password
    or its hash."""
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": (user.user_metadata or {}).get("name"),
            "role": (user.user_metadata or {}).get("role", "agent"),
        },
    }


@router.post("/signup")
def agent_signup(body: AuthBody):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    display_name = body.name or body.email.split("@")[0]

    # Supabase hashes `password` with bcrypt server-side before storing it
    # in `auth.users.encrypted_password`. The plaintext is never persisted.
    try:
        created = supabase.auth.admin.create_user(
            {
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {
                    "role": "agent",
                    "name": display_name,
                },
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Immediately exercise the login path so the new account is only considered
    # "created" if the bcrypt comparison against the freshly-stored hash works.
    try:
        session = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Account created but sign-in failed: {e}",
        ) from e

    if not session or not session.session:
        raise HTTPException(
            status_code=400,
            detail="Account created but no session returned",
        )

    return _session_payload(session.session, session.user or created.user)


@router.post("/login")
def agent_login(body: AuthBody):
    """Hand the plaintext password to Supabase, which bcrypt-hashes it and
    compares against the stored hash. If the hashes don't match, Supabase
    raises and we return 401. The frontend only ever gets a session token."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    try:
        result = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password") from e

    if not result or not result.session or not result.user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return _session_payload(result.session, result.user)


@router.get("/session")
def agent_session(authorization: Optional[str] = Header(default=None)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        result = supabase.auth.get_user(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid session") from e

    if not result:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = result.user
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": (user.user_metadata or {}).get("name"),
            "role": (user.user_metadata or {}).get("role", "agent"),
        }
    }
