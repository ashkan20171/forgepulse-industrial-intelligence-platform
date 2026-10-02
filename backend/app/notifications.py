from collections import deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from pydantic import BaseModel
class Notification(BaseModel): id:str; title:str; message:str; level:str="INFO"; created_at:datetime; read:bool=False
class NotificationCenter:
    def __init__(self): self._lock=RLock(); self._items=deque(maxlen=200)
    def push(self,title,message,level="INFO"):
        with self._lock:
            item=Notification(id=str(uuid4()),title=title,message=message,level=level,created_at=datetime.now(timezone.utc));self._items.appendleft(item);return item
    def list(self):
        with self._lock:return list(self._items)
    def read(self,nid):
        with self._lock:
            for i,x in enumerate(self._items):
                if x.id==nid:self._items[i]=x.model_copy(update={"read":True});return self._items[i]
        return None
notifications=NotificationCenter()
