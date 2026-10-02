from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
import base64, hmac, json, secrets
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from .config import settings
from sqlalchemy import select
from .persistence import UserRow, session_scope
from .distributed import limiter as distributed_limiter
from .security_zero_trust import ROLE_PERMISSIONS_V18, password_policy

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

class RefreshRequest(BaseModel):
    refresh_token: str

class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,50}$")
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(pattern=r"^(ADMIN|OPERATOR|VIEWER)$")

class UserPatch(BaseModel):
    display_name: str | None = None
    role: str | None = Field(default=None, pattern=r"^(ADMIN|OPERATOR|VIEWER)$")
    enabled: bool | None = None

class UserInfo(BaseModel):
    username: str
    display_name: str
    role: str
    permissions: list[str]
    enabled: bool = True

ROLE_PERMISSIONS = ROLE_PERMISSIONS_V18

def _password_hash(password: str, salt: str | None = None) -> str:
    salt_bytes = base64.urlsafe_b64decode(salt.encode()) if salt else secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt_bytes, 180_000)
    return f"{base64.urlsafe_b64encode(salt_bytes).decode()}${base64.urlsafe_b64encode(digest).decode()}"

def _verify(password: str, encoded: str) -> bool:
    salt, expected = encoded.split("$", 1)
    return hmac.compare_digest(_password_hash(password, salt).split("$", 1)[1], expected)

class UserRepository:
    def seed(self):
        with session_scope() as s:
            if s.scalar(select(UserRow.username).limit(1)): return
            for username,password,name,role in [("admin",settings.DEMO_ADMIN_PASSWORD,"Platform Administrator","ADMIN"),("operator",settings.DEMO_OPERATOR_PASSWORD,"Control Room Operator","OPERATOR"),("viewer",settings.DEMO_VIEWER_PASSWORD,"Read-only Viewer","VIEWER")]:
                s.add(UserRow(username=username,password_hash=_password_hash(password),display_name=name,role=role,enabled=True))
    def info(self,username):
        with session_scope() as s:
            row=s.get(UserRow,username)
            return UserInfo(username=row.username,display_name=row.display_name,role=row.role,permissions=ROLE_PERMISSIONS[row.role],enabled=row.enabled) if row else None
    def authenticate(self,username,password):
        with session_scope() as s:
            row=s.get(UserRow,username)
            if not row or not row.enabled or not _verify(password,row.password_hash): return None
            return UserInfo(username=row.username,display_name=row.display_name,role=row.role,permissions=ROLE_PERMISSIONS[row.role],enabled=row.enabled)
    def list(self):
        with session_scope() as s:return [UserInfo(username=r.username,display_name=r.display_name,role=r.role,permissions=ROLE_PERMISSIONS[r.role],enabled=r.enabled) for r in s.scalars(select(UserRow).order_by(UserRow.username)).all()]
    def create(self,body):
        ok, missing = password_policy(body.password)
        if not ok: raise HTTPException(422, "Password policy: " + ", ".join(missing))
        with session_scope() as s:
            if s.get(UserRow,body.username): raise HTTPException(409,"Username already exists")
            s.add(UserRow(username=body.username,display_name=body.display_name,password_hash=_password_hash(body.password),role=body.role,enabled=True))
        return self.info(body.username)
    def patch(self,username,body):
        with session_scope() as s:
            row=s.get(UserRow,username)
            if not row:return None
            for key,value in body.model_dump(exclude_none=True).items(): setattr(row,key,value)
        return self.info(username)

users = UserRepository()

def _b64(raw: bytes) -> str: return base64.urlsafe_b64encode(raw).decode().rstrip("=")
def _encode(payload: dict) -> str:
    header = _b64(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(settings.AUTH_SECRET.encode(), f"{header}.{body}".encode(), sha256).digest())
    return f"{header}.{body}.{signature}"
def _decode(token: str, expected_type: str) -> dict:
    try:
        header, body, signature = token.split(".")
        expected = _b64(hmac.new(settings.AUTH_SECRET.encode(), f"{header}.{body}".encode(), sha256).digest())
        if not hmac.compare_digest(signature, expected): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if payload.get("typ") != expected_type or payload["exp"] < int(datetime.now(timezone.utc).timestamp()): raise ValueError
        return payload
    except Exception as exc: raise HTTPException(401, "Invalid or expired token") from exc


def create_token_pair(username: str) -> dict:
    now = datetime.now(timezone.utc)
    access = _encode({"sub":username,"typ":"access","iat":int(now.timestamp()),"exp":int((now+timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)).timestamp())})
    jti = secrets.token_urlsafe(18)
    refresh = _encode({"sub":username,"typ":"refresh","jti":jti,"iat":int(now.timestamp()),"exp":int((now+timedelta(days=settings.REFRESH_TOKEN_DAYS)).timestamp())})
    return {"access_token":access,"refresh_token":refresh,"token_type":"bearer","expires_in":settings.ACCESS_TOKEN_MINUTES*60}
def refresh_tokens(token: str) -> dict:
    payload = _decode(token, "refresh")
    if distributed_limiter.revoked(payload["jti"]): raise HTTPException(401, "Refresh token revoked")
    user = users.info(payload["sub"])
    if not user or not user.enabled: raise HTTPException(401, "Unknown or disabled user")
    distributed_limiter.revoke(payload["jti"], settings.REFRESH_TOKEN_DAYS*86400)
    return create_token_pair(user.username)
def revoke_refresh(token: str) -> None:
    payload = _decode(token, "refresh"); distributed_limiter.revoke(payload["jti"], settings.REFRESH_TOKEN_DAYS*86400)
def authenticate(username: str, password: str): return users.authenticate(username, password)
def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401, "Authentication required")
    payload = _decode(authorization[7:], "access")
    user = users.info(payload["sub"])
    if not user or not user.enabled: raise HTTPException(401, "Unknown or disabled user")
    return user

def user_from_access_token(token: str) -> UserInfo:
    payload = _decode(token, "access")
    user = users.info(payload["sub"])
    if not user or not user.enabled: raise HTTPException(401, "Unknown or disabled user")
    return user
