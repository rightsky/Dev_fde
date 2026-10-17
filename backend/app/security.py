"""비밀번호 해시, JWT, 권한 의존성."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

_ALGO = "HS256"
_bearer = HTTPBearer(auto_error=False)
_runtime_secret = secrets.token_urlsafe(48)


def _secret() -> str:
    return get_settings().secret_key or _runtime_secret


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8")[:72], bcrypt.gensalt()).decode("ascii")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8")[:72], hashed.encode("ascii"))
    except ValueError:
        return False


def create_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=get_settings().token_minutes)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다")
    if cred is None:
        raise unauthorized
    try:
        data = jwt.decode(cred.credentials, _secret(), algorithms=[_ALGO])
        uid = int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None
    user = db.get(User, uid)
    if user is None or not user.active:
        raise unauthorized
    if user.password_changed_at is not None and int(data.get("iat", 0)) < int(user.password_changed_at.timestamp()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "비밀번호가 바뀌어 다시 로그인해야 합니다")
    return user


def require_writer(user: User = Depends(current_user)) -> User:
    if user.role not in ("admin", "worker"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "열람 전용 계정은 변경할 수 없습니다")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자 권한이 필요합니다")
    return user
