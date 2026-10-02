from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
import hashlib, secrets
from pydantic import BaseModel, Field
from sqlalchemy import select
from .store import store
from .operations import operations
from .persistence import IncidentRow, ApiKeyRow, session_scope
from .distributed import limiter
class IncidentCreate(BaseModel):
    asset_id:str; title:str=Field(min_length=3,max_length=140); severity:str=Field(default='HIGH',pattern=r'^(LOW|MEDIUM|HIGH|CRITICAL)$'); description:str=Field(default='',max_length=1000)
class IncidentService:
    def _dict(self,x):return {'id':x.id,'asset_id':x.asset_id,'title':x.title,'severity':x.severity,'description':x.description,'status':x.status,'owner':x.owner,'opened_at':x.opened_at.isoformat(),'resolved_at':x.resolved_at.isoformat() if x.resolved_at else None}
    def list(self):
        with session_scope() as s:return [self._dict(x) for x in s.scalars(select(IncidentRow).order_by(IncidentRow.opened_at.desc())).all()]
    def create(self,body,owner):
        row=IncidentRow(id=f"INC-{uuid4().hex[:8].upper()}",**body.model_dump(),status='OPEN',owner=owner,opened_at=datetime.now(timezone.utc))
        with session_scope() as s:s.add(row)
        return self._dict(row)
    def resolve(self,iid):
        with session_scope() as s:
            x=s.get(IncidentRow,iid)
            if not x:return None
            x.status='RESOLVED'; x.resolved_at=datetime.now(timezone.utc); s.flush(); return self._dict(x)
incidents=IncidentService()
class ApiKeyCreate(BaseModel):
    name:str=Field(min_length=3,max_length=80)
    scopes:list[str]=Field(default_factory=lambda:['telemetry:read'])
class ApiKeyService:
    def __init__(self): self._scopes={}
    def _public(self,x):return {'id':x.id,'name':x.name,'prefix':x.prefix,'created_at':x.created_at.isoformat(),'enabled':x.enabled,'scopes':self._scopes.get(x.id,['telemetry:read'])}
    def list(self):
        with session_scope() as s:return [self._public(x) for x in s.scalars(select(ApiKeyRow).order_by(ApiKeyRow.created_at.desc())).all()]
    def create(self,name,scopes=None):
        raw='iiot_'+secrets.token_urlsafe(28); row=ApiKeyRow(id=uuid4().hex[:12],name=name,prefix=raw[:12],key_hash=hashlib.sha256(raw.encode()).hexdigest(),created_at=datetime.now(timezone.utc),enabled=True)
        with session_scope() as s:s.add(row)
        self._scopes[row.id]=scopes or ['telemetry:read']
        return {**self._public(row),'api_key':raw}
api_keys=ApiKeyService()
def hierarchy():
    plants={'Tehran Smart Plant':{'Line A':[],'Line B':[],'Utilities':[]}}
    for m in store.machines():
        line='Utilities' if 'Utility' in m.location else m.location if m.location in ('Line A','Line B') else 'Line A'; plants['Tehran Smart Plant'].setdefault(line,[]).append(m.model_dump())
    return [{'plant':p,'lines':[{'name':n,'assets':a} for n,a in lines.items()]} for p,lines in plants.items()]
def reliability_kpis():
    work=operations.work_orders(); closed=[x for x in work if x.status=='COMPLETED']; opened=[x for x in work if x.status=='OPEN']; mttr=round(2.4+len(opened)*.35,1); mtbf=round(max(24,168-len(store.alerts())*3.5),1); latest=store.latest(); energy=round(sum(((x.rpm or 1200)/1200)*(1+x.anomaly_score*.18)*18 for x in latest),1)
    return {'mtbf_hours':mtbf,'mttr_hours':mttr,'open_incidents':sum(x['status']=='OPEN' for x in incidents.list()),'estimated_power_kw':energy,'closed_work_orders':len(closed),'reliability_score':round(min(99,max(0,100-(len(opened)*4+len(store.alerts())*1.5))),1)}
