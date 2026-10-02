from __future__ import annotations
import hashlib, time
from redis import Redis
from .config import settings
redis_client=Redis.from_url(settings.REDIS_URL,decode_responses=True,socket_connect_timeout=1,socket_timeout=1)
def redis_ping():
    try:return bool(redis_client.ping())
    except Exception:return False
class DistributedRateLimiter:
    def allow(self,key:str,limit:int|None=None,window:int=60)->bool:
        limit=limit or settings.RATE_LIMIT_PER_MINUTE; bucket=int(time.time()//window); k=f'ratelimit:{key}:{bucket}'
        try:
            value=redis_client.incr(k)
            if value==1: redis_client.expire(k,window+2)
            return value<=limit
        except Exception:return True
    def revoke(self,token:str,ttl:int):
        try:redis_client.setex('revoked:'+hashlib.sha256(token.encode()).hexdigest(),ttl,'1')
        except Exception:pass
    def revoked(self,token:str)->bool:
        try:return bool(redis_client.exists('revoked:'+hashlib.sha256(token.encode()).hexdigest()))
        except Exception:return False
limiter=DistributedRateLimiter()
