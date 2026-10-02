from __future__ import annotations
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from threading import RLock
from uuid import uuid4
from pydantic import BaseModel, Field
from .event_engine import event_bus
from .flagship import incidents, IncidentCreate
from .notifications import notifications
from .store import store

class RuleCreate(BaseModel):
    name:str=Field(min_length=3,max_length=100); metric:str=Field(pattern=r'^(temperature|vibration|pressure|rpm|anomaly_score)$'); operator:str=Field(pattern=r'^(>=|>|<=|<)$'); threshold:float; severity:str=Field(default='WARNING',pattern=r'^(INFO|WARNING|HIGH|CRITICAL)$'); enabled:bool=True

class ModelVersion(BaseModel):
    id:str; name:str; version:str; stage:str; created_at:datetime; description:str

class AutonomousOps:
    def __init__(self):
        self._lock=RLock(); self._correlations=deque(maxlen=300); self._last_incident={}
        self.models=[ModelVersion(id='condition-baseline-v1',name='Condition Baseline',version='1.0.0',stage='PRODUCTION',created_at=datetime.now(timezone.utc),description='Explainable statistical condition baseline.'),ModelVersion(id='onnx-adapter-slot',name='ONNX Adapter',version='0.1.0',stage='READY',created_at=datetime.now(timezone.utc),description='Deployment seam for a validated ONNX predictive model.')]
    def correlate(self,event):
        now=datetime.now(timezone.utc); recent=[x for x in event_bus.recent(80) if x['asset_id']==event.asset_id and datetime.fromisoformat(x['timestamp'])>=now-timedelta(minutes=10)]
        types=sorted(set(x['event_type'] for x in recent)); score=min(100,25*len(recent)+15*len(types)); severity='CRITICAL' if score>=80 else 'HIGH' if score>=55 else 'MEDIUM'
        item={'id':f'COR-{uuid4().hex[:8].upper()}','asset_id':event.asset_id,'score':score,'severity':severity,'signals':types,'event_count':len(recent),'created_at':now.isoformat(),'summary':f'{len(recent)} related signals across {len(types)} event types in a 10-minute window.'}
        with self._lock:self._correlations.appendleft(item)
        if score>=55:self._auto_incident(event.asset_id,severity,item)
        return item
    def _auto_incident(self,asset_id,severity,corr):
        now=datetime.now(timezone.utc); last=self._last_incident.get(asset_id)
        if last and now-last<timedelta(minutes=20):return
        title=f'Correlated condition risk on {asset_id}'; body=IncidentCreate(asset_id=asset_id,title=title,severity='CRITICAL' if severity=='CRITICAL' else 'HIGH',description=f"Auto-created from correlation {corr['id']}: {corr['summary']}")
        try:
            incident=incidents.create(body,'AUTOMATION'); self._last_incident[asset_id]=now
            notifications.push('Incident auto-created',f"{incident['id']} · {asset_id} · {severity}",severity)
            event_bus.publish('INCIDENT_AUTO_CREATED',asset_id,severity,title,{'incident_id':incident['id'],'correlation_id':corr['id']})
        except Exception: pass
    def correlations(self):
        with self._lock:return list(self._correlations)
    def root_cause(self,asset_id):
        hist=store.history(asset_id,120)
        events=[x for x in event_bus.recent(200) if x['asset_id']==asset_id]
        if not hist:return {'asset_id':asset_id,'confidence':0,'primary_cause':'Insufficient telemetry','evidence':[],'actions':['Collect additional telemetry.']}
        latest=hist[-1]; evidence=[]; candidates=[]
        if latest.vibration>=7:candidates.append(('Mechanical vibration / alignment',0.86)); evidence.append(f'Vibration {latest.vibration:.2f} mm/s')
        if latest.temperature>=75:candidates.append(('Thermal stress / cooling degradation',0.78)); evidence.append(f'Temperature {latest.temperature:.1f}°C')
        if latest.anomaly_score>=.7:candidates.append(('Multi-signal operating deviation',0.72)); evidence.append(f'Anomaly score {latest.anomaly_score:.0%}')
        cause,conf=max(candidates,key=lambda x:x[1]) if candidates else ('No dominant failure signature detected',.48)
        return {'asset_id':asset_id,'confidence':conf,'primary_cause':cause,'evidence':evidence+[f'{len(events)} recent domain events'],'actions':['Inspect bearings, alignment and lubrication.' if 'vibration' in cause.lower() else 'Verify cooling, load and thermal interfaces.','Review correlated event timeline before parts replacement.','Validate finding during next condition-based inspection.']}
    def model_registry(self):return [x.model_dump(mode='json') for x in self.models]

autonomous=AutonomousOps()

def _handler(event): autonomous.correlate(event)
event_bus.subscribe('RULE_TRIGGERED',_handler); event_bus.subscribe('ANOMALY_DETECTED',_handler)
