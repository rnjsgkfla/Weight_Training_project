"""
auth.py — 이메일 회원가입·로그인 (bcrypt 비밀번호 해시 + JWT 액세스 토큰)

앱은 로그인 응답의 access_token 을 저장해 두고, 이후 요청에
`Authorization: Bearer <token>` 헤더로 보낸다. 토큰 유효기간은 30일(만료되면 다시 로그인).

JWT_SECRET 환경변수가 없으면 임시 비밀키를 만들어 쓴다 → 서버를 재시작하면 기존 토큰이
모두 무효가 된다. 배포 환경에서는 반드시 JWT_SECRET 을 설정한다.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

import media
from db import User, as_utc, get_db
from schemas import LoginRequest, SignupRequest, TokenResponse, UserOut

log = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=30)

_JWT_SECRET = os.environ.get("JWT_SECRET")
if not _JWT_SECRET:
    log.warning("JWT_SECRET 미설정: 임시 비밀키 사용 (재시작 시 로그인 토큰이 모두 무효화됨)")
    _JWT_SECRET = secrets.token_urlsafe(32)

router = APIRouter(tags=["auth"])
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="로그인이 필요합니다.",
    headers={"WWW-Authenticate": "Bearer"},
)


# ── 비밀번호 / 토큰 ────────────────────────────────────────────────────────────
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # bcrypt 입력 한도(72바이트) 초과 등
        return False


def create_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def _user_from_token(token, db):
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHORIZED
    user = db.get(User, user_id)
    if user is None:  # 탈퇴한 계정의 토큰
        raise _UNAUTHORIZED
    return user


# ── 의존성 ─────────────────────────────────────────────────────────────────────
def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: Session = Depends(get_db)):
    """로그인 필수 엔드포인트용."""
    if cred is None:
        raise _UNAUTHORIZED
    return _user_from_token(cred.credentials, db)


def get_optional_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                      db: Session = Depends(get_db)):
    """로그인 선택 엔드포인트용 (/analyze). 토큰이 없으면 None, 잘못된 토큰이면 401."""
    if cred is None:
        return None
    return _user_from_token(cred.credentials, db)


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────
@router.post("/auth/signup", response_model=TokenResponse, status_code=201)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """회원가입 후 바로 로그인 토큰을 돌려준다."""
    if len(req.password.encode()) > 72:  # bcrypt 는 72바이트까지만 쓴다
        raise HTTPException(status_code=400, detail="비밀번호가 너무 깁니다.")
    email = req.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")
    user = User(email=email, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_token(user.id))


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == req.email.lower()))
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    return TokenResponse(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, created_at=as_utc(user.created_at))


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """회원 탈퇴: 계정과 모든 운동 기록·이미지를 삭제한다."""
    session_ids = [s.id for s in user.sessions]
    db.delete(user)
    db.commit()
    for sid in session_ids:
        media.delete_session_media(sid)
