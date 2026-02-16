from datetime import datetime, timedelta, timezone
import hashlib
import jwt
from fastapi import Depends, Header, HTTPException, status
from passlib.hash import bcrypt
import bcrypt
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from db_models import User

AUTH_ERROR = {"message": "인증 에러"}


def create_jwt_token(user_id: str) -> str:
    payload = {
        "id": user_id,
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=settings.jwt_expires_sec),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _normalize_password(password: str) -> bytes:
    # bcrypt의 72바이트 제한을 피하기 위해 SHA-256으로 전처리 (결과는 항상 32바이트)
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    # 1. SHA-256 바이트 데이터를 가져옴
    normalized = _normalize_password(password)
    
    # 2. bcrypt는 바이트 데이터를 바로 받을 수 있음
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(normalized, salt)
    
    # 3. DB 저장을 위해 문자열로 변환
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    # 1. 로그인 시 입력받은 비번도 똑같이 SHA-256 바이트로 변환
    normalized = _normalize_password(password)
    
    # 2. DB에 저장된 hashed 문자열을 바이트로 변환해서 비교
    # bcrypt.checkpw(입력받은_바이트, DB에_있던_바이트)
    return bcrypt.checkpw(normalized, hashed.encode('utf-8'))


def get_current_user_context(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not (authorization and authorization.startswith("Bearer ")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_ERROR)

    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_ERROR)

    user_id = decoded.get("id")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_ERROR)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_ERROR)

    return {"user": user, "token": token}


def get_optional_user_context(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not (authorization and authorization.startswith("Bearer ")):
        return {"user": None, "token": None}

    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return {"user": None, "token": None}

    user_id = decoded.get("id")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return {"user": None, "token": None}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"user": None, "token": None}

    return {"user": user, "token": token}
