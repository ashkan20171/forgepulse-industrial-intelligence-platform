from datetime import datetime, timezone
from threading import RLock
from pydantic import BaseModel, Field

class DevicePatch(BaseModel):
    firmware: str|None=Field(default=None,max_length=40)
    maintenance_mode: bool|None=None
class Device(BaseModel):
    asset_id:str; protocol:str="MQTT"; firmware:str="1.4.2"; maintenance_mode:bool=False; last_seen:datetime|None=None; twin_state:str="READY"
class DeviceRegistry:
    def __init__(self): self._lock=RLock(); self._items={k:Device(asset_id=k,firmware=v) for k,v in {"motor_01":"2.1.0","pump_01":"1.8.4","fan_01":"1.5.7"}.items()}
    def list(self):
        with self._lock:return list(self._items.values())
    def sync(self,asset_id):
        with self._lock:
            item=self._items.setdefault(asset_id,Device(asset_id=asset_id)); self._items[asset_id]=item.model_copy(update={"last_seen":datetime.now(timezone.utc),"twin_state":"SYNCHRONIZED"}); return self._items[asset_id]
    def patch(self,asset_id,**changes):
        with self._lock:
            item=self._items.get(asset_id)
            if not item:return None
            self._items[asset_id]=item.model_copy(update={k:v for k,v in changes.items() if v is not None}); return self._items[asset_id]
devices=DeviceRegistry()
