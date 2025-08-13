from collections import defaultdict
from config import settings
from fastapi import HTTPException

class ActiveBatchLimiter:
    _global: set[str] = set()
    _by_key: defaultdict[str, set[str]] = defaultdict(set)

    def register(self, api_key: str, batch_id: str):
        if len(self._global) >= settings.active_batch_limit:
            raise HTTPException(429, headers={"Retry-After": "60"},
                                detail="active_batch_limit")
        if len(self._by_key[api_key]) >= settings.per_key_batch_limit:
            raise HTTPException(429, headers={"Retry-After": "60"},
                                detail="per_key_batch_limit")
        self._global.add(batch_id)
        self._by_key[api_key].add(batch_id)

    def finish(self, api_key: str, batch_id: str):
        self._global.discard(batch_id)
        self._by_key[api_key].discard(batch_id)

limiter = ActiveBatchLimiter()
