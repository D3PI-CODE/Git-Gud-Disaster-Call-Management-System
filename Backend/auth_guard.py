"""JWT auth guard for protected agent routes.

The frontend stores the Supabase-issued access token in sessionStorage and
attaches it to every API call as `Authorization: Bearer <jwt>`. This module
decodes that JWT (via the Supabase server SDK, which validates signature +
expiry against the project's JWKS) and exposes the authenticated agent to
FastAPI routes through a `Depends(get_current_agent)` dependency.

`CurrentAgent.agent_id` is the Supabase Auth user UUID. It is the exact same
value used by `incidents.agent_id` and `agents.id`, so any route that needs to
filter or mutate "my cases" can pass it straight through to the data layer.
"""

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException

from supabase_client import supabase


@dataclass(frozen=True)
class CurrentAgent:
    """The authenticated agent decoded from a Bearer JWT."""

    agent_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: str = "agent"


def _decode_agent_from_token(token: str) -> CurrentAgent:
    """Validate a Supabase access token and return the agent it represents.

    Raises `HTTPException(401)` on any decode/validation failure. We never
    surface the underlying error to the client to avoid leaking JWT internals.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    try:
        result = supabase.auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    user = getattr(result, "user", None) if result else None
    if not user or not getattr(user, "id", None):
        raise HTTPException(status_code=401, detail="Invalid session")

    metadata = getattr(user, "user_metadata", None) or {}
    return CurrentAgent(
        agent_id=user.id,
        email=getattr(user, "email", None),
        name=metadata.get("name"),
        role=metadata.get("role", "agent"),
    )


def resolve_agent_from_header(authorization: Optional[str]) -> CurrentAgent:
    """Imperative variant of `get_current_agent` for endpoints that mix auth
    modes (e.g. the triage webhook accepts EITHER an agent JWT OR a shared
    webhook secret). Most routes should prefer `Depends(get_current_agent)`.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode_agent_from_token(token)


def get_current_agent(
    authorization: Optional[str] = Header(default=None),
) -> CurrentAgent:
    """FastAPI dependency: extract the authenticated agent from the
    `Authorization: Bearer <jwt>` header. Use as:

        @router.get("/secure")
        def secure(agent: CurrentAgent = Depends(get_current_agent)): ...
    """
    return resolve_agent_from_header(authorization)


def get_current_agent_id(
    agent: CurrentAgent = Depends(get_current_agent),
) -> str:
    """Convenience dependency for routes that only need the agent UUID."""
    return agent.agent_id
