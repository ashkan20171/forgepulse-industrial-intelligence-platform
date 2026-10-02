from __future__ import annotations
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from pydantic import BaseModel, Field
from .store import store
from .operations import operations
from .flagship import incidents, hierarchy

class DowntimeCreate(BaseModel):
    asset_id:str; reason:str=Field(min_length=3,max_length=160); category:str=Field(default='UNPLANNED',pattern=r'^(PLANNED|UNPLANNED|QUALITY|MATERIAL|CHANGEOVER)$'); minutes:int=Field(gt=0,le=1440)
class SparePartCreate(BaseModel):
    sku:str=Field(min_length=2,max_length=40); name:str=Field(min_length=2,max_length=100); quantity:int=Field(ge=0); reorder_point:int=Field(ge=0); unit:str='pcs'
class RcaReview(BaseModel): decision:str=Field(pattern=r'^(APPROVED|REJECTED)$'); note:str=Field(default='',max_length=500)

class ManufacturingOps:
    def __init__(self):
        self.lock=RLock(); self.downtime=[]; self.parts={
          'BRG-6205':{'sku':'BRG-6205','name':'6205 bearing','quantity':8,'reorder_point':4,'unit':'pcs'},
          'FLT-AIR-01':{'sku':'FLT-AIR-01','name':'Compressor air filter','quantity':2,'reorder_point':3,'unit':'pcs'},
          'OIL-ISO46':{'sku':'OIL-ISO46','name':'Hydraulic oil ISO VG 46','quantity':36,'reorder_point':20,'unit':'L'}}
        self.rca_reviews={}; self.escalations=[{'severity':'CRITICAL','after_minutes':5,'route':'Reliability Lead + Plant Manager'},{'severity':'HIGH','after_minutes':15,'route':'Maintenance Supervisor'},{'severity':'WARNING','after_minutes':30,'route':'Shift Lead'}]
    def shifts(self):
        return [{'id':'SHIFT-A','name':'Morning','start':'06:00','end':'14:00'},{'id':'SHIFT-B','name':'Evening','start':'14:00','end':'22:00'},{'id':'SHIFT-C','name':'Night','start':'22:00','end':'06:00'}]
    def record_downtime(self,b:DowntimeCreate,actor:str):
        item={'id':f'DT-{uuid4().hex[:8].upper()}','asset_id':b.asset_id,'reason':b.reason,'category':b.category,'minutes':b.minutes,'reported_by':actor,'created_at':datetime.now(timezone.utc).isoformat()}
        with self.lock:self.downtime.insert(0,item)
        return item
    def dashboard(self):
        latest=store.latest(); ms=store.machines(); enabled=[m for m in ms if m.enabled]; reporting={x.machine_id for x in latest}
        availability=(sum(m.id in reporting for m in enabled)/len(enabled)*100) if enabled else 100
        avg_anomaly=sum(x.anomaly_score for x in latest)/max(1,len(latest)); performance=max(0,100-avg_anomaly*35); quality=max(0,100-sum(x.status.value=='CRITICAL' for x in latest)*4); oee=availability*performance*quality/10000
        dt=sum(x['minutes'] for x in self.downtime); open_inc=sum(x['status']=='OPEN' for x in incidents.list()); low=sum(p['quantity']<=p['reorder_point'] for p in self.parts.values())
        losses={k:sum(x['minutes'] for x in self.downtime if x['category']==k) for k in ['UNPLANNED','PLANNED','QUALITY','MATERIAL','CHANGEOVER']}
        return {'oee':round(oee,1),'availability':round(availability,1),'performance':round(performance,1),'quality':round(quality,1),'downtime_minutes':dt,'open_incidents':open_inc,'low_stock_parts':low,'downtime_losses':losses,'sites':len(hierarchy()),'assets':len(ms)}
    def add_part(self,b:SparePartCreate):
        item=b.model_dump(); self.parts[b.sku]=item; return item
    def review_rca(self,incident_id,b:RcaReview,actor):
        item={'incident_id':incident_id,'decision':b.decision,'note':b.note,'reviewed_by':actor,'reviewed_at':datetime.now(timezone.utc).isoformat()}; self.rca_reviews[incident_id]=item; return item
manufacturing=ManufacturingOps()
