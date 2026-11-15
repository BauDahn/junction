"""Request throttling and daily limits for public endpoints."""
import logging
import os
import threading
import time
from datetime import datetime, timezone

from fastapi import HTTPException, Request

logger = logging.getLogger("uvicorn.error")
_lock = threading.Lock()
_counts = {}
_negative = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") if os.getenv("TRUST_PROXY") == "1" else None
    return (forwarded.split(",", 1)[0].strip() if forwarded else None) or (request.client.host if request.client else "unknown")


def account_for(authorization: str | None):
    if authorization and authorization.startswith("Bearer "):
        from accounts.routes import _authenticated
        return _authenticated(authorization)
    return None


def identity(request: Request, user=None):
    return f"account:{user['id']}" if user else f"ip:{client_ip(request)}"


def _limit(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _increment(key: str, ttl: int) -> int:
    try:
        from canonizador.cache import remote_from_env
        remote = remote_from_env()
        if remote is not None:
            ok, result = remote._run(lambda client: _redis_increment(client, key, ttl))
            if ok:
                return int(result)
    except Exception:
        pass
    now = time.time()
    with _lock:
        count, expires = _counts.get(key, (0, now + ttl))
        if expires <= now:
            count, expires = 0, now + ttl
        count += 1
        _counts[key] = (count, expires)
        return count


def _redis_increment(client, key, ttl):
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, ttl)
    return pipe.execute()[0]


def enforce(request: Request, bucket: str, subject: str, default: int, period: int):
    now = int(time.time())
    window = now // period
    name = f"abuse:v1:{bucket}:{subject}:{window}"
    count = _increment(name, period + 2)
    if count > _limit(f"{bucket.upper()}_LIMIT", default):
        retry = period - now % period
        logger.warning("request limited client=%s route=%s", subject, request.url.path)
        raise HTTPException(429, "Too many requests. Please retry later.", headers={"Retry-After": str(retry)})


def daily(request: Request, bucket: str, subject: str, default: int):
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    count = _increment(f"abuse:v1:daily:{bucket}:{subject}:{day}", 90000)
    if count > _limit(f"{bucket.upper()}_DAILY_LIMIT", default):
        logger.warning("daily limit reached client=%s route=%s", subject, request.url.path)
        raise HTTPException(429, "Daily request limit reached.", headers={"Retry-After": "86400"})


def account_daily(request: Request, user):
    subject = f"account:{user['id']}"
    daily(request, "cala_account", subject, 150)


def negative_hit(key: str) -> bool:
    now = time.time()
    with _lock:
        expires = _negative.get(key, 0)
        if expires <= now:
            _negative.pop(key, None)
            return False
        return True


def negative_put(key: str, ttl: int = 3600):
    with _lock:
        _negative[key] = time.time() + ttl

