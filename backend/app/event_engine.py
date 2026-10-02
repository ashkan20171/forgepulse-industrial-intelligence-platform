from __future__ import annotations
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

@dataclass
class DomainEvent:
    id: str; event_type: str; asset_id: str; severity: str; message: str; timestamp: str; payload: dict

class EventBus:
    """Small in-process domain event bus. Handlers are isolated so telemetry ingestion remains resilient."""
    def __init__(self): self._handlers={}; self._events=deque(maxlen=500); self._lock=RLock()
    def subscribe(self,event_type,handler): self._handlers.setdefault(event_type,[]).append(handler)
    def publish(self,event_type,asset_id,severity,message,payload=None):
        event=DomainEvent(str(uuid4()),event_type,asset_id,severity,message,datetime.now(timezone.utc).isoformat(),payload or {})
        with self._lock: self._events.appendleft(event)
        for handler in self._handlers.get(event_type,[]):
            try: handler(event)
            except Exception: pass
        return asdict(event)
    def recent(self,limit=100):
        with self._lock: return [asdict(x) for x in list(self._events)[:limit]]

event_bus=EventBus()
