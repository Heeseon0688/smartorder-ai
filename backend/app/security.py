import hashlib
import secrets
import time
from collections import defaultdict, deque
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .db import get_db
from .models import AdminSession, AdminUser, utcnow

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(24))

def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def resolve_admin(db, token):
    session = db.get(AdminSession, digest(token or ''))
    if not session or session.expires_at <= utcnow():
        return None
    return db.get(AdminUser, session.admin_id)

def admin_user(request: Request, db: Session = Depends(get_db)):
    admin = resolve_admin(db, request.cookies.get('smartorder_session'))
    if not admin:
        raise HTTPException(401, '관리자 로그인이 필요합니다.')
    return admin

# Single-process MVP. Use Redis-backed limits when deploying multiple workers.
class RateLimiter:
    def __init__(self):
        self.buckets = defaultdict(deque)
    def check(self, key, limit=20, window=60):
        now = time.monotonic()
        bucket = self.buckets[key]
        while bucket and bucket[0] < now-window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.')
        bucket.append(now)
        if len(self.buckets) > 10000:
            self.buckets = defaultdict(deque, {k:v for k,v in self.buckets.items() if v and v[-1] > now-window})
limiter = RateLimiter()
