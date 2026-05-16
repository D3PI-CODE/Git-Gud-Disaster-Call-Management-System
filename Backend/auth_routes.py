from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, field_validator

from supabase_client import supabase

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthBody(BaseModel):
    email: str
    password: str
    name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or len(email) < 5:
            raise ValueError("Invalid email address")
        return email


def _session_payload(session, user):
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

    try:
        session = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Account created but sign-in failed: {e}",
        ) from e

    if not session.session:
        raise HTTPException(status_code=400, detail="Account created but no session returned")

    return _session_payload(session.session, session.user or created.user)


@router.post("/login")
def agent_login(body: AuthBody):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    try:
        result = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password") from e

    if not result.session:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return _session_payload(result.session, result.user)


@router.get("/session")
def agent_session(authorization: str | None = Header(default=None)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        result = supabase.auth.get_user(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid session") from e

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
