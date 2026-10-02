from __future__ import annotations
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from pydantic import BaseModel, Field
from .store import store

class ProductionOrderCreate(BaseModel):
    product_sku: str = Field(min_length=2, max_length=40)
    line: str = Field(min_length=2, max_length=80)
    target_qty: int = Field(gt=0, le=1_000_000)
    planned_cycle_seconds: float = Field(gt=0, le=86400)
    shift_id: str = 'SHIFT-A'

class ProductionReport(BaseModel):
    good_qty: int = Field(ge=0)
    reject_qty: int = Field(ge=0)
    actual_cycle_seconds: float = Field(gt=0, le=86400)

class QualityInspectionCreate(BaseModel):
    order_id: str
    characteristic: str = Field(min_length=2, max_length=100)
    result: str = Field(pattern=r'^(PASS|FAIL|HOLD)$')
    value: str = Field(default='', max_length=100)
    note: str = Field(default='', max_length=300)

class MachineStatePatch(BaseModel):
    state: str = Field(pattern=r'^(RUNNING|IDLE|CHANGEOVER|STARVED|BLOCKED|DOWN|MAINTENANCE)$')
    reason: str = Field(default='', max_length=180)

class HandoverCreate(BaseModel):
    shift_id: str
    summary: str = Field(min_length=5, max_length=1000)
    safety_note: str = Field(default='', max_length=500)
    priority_next_shift: str = Field(default='', max_length=500)

class MESOps:
    def __init__(self):
        self.lock=RLock()
        self.products={
          'SKU-PUMP-01':{'sku':'SKU-PUMP-01','name':'Industrial Pump Assembly','revision':'C','standard_cycle_seconds':72},
          'SKU-MOTOR-07':{'sku':'SKU-MOTOR-07','name':'Servo Motor Module','revision':'B','standard_cycle_seconds':48},
          'SKU-VALVE-12':{'sku':'SKU-VALVE-12','name':'Control Valve Pack','revision':'A','standard_cycle_seconds':36}}
        self.orders=[]; self.inspections=[]; self.handovers=[]; self.machine_states={}
        self._seed()
    def _now(self): return datetime.now(timezone.utc).isoformat()
    def _seed(self):
        self.orders=[
          {'id':'PO-24031','product_sku':'SKU-PUMP-01','line':'Assembly Line 1','target_qty':480,'good_qty':326,'reject_qty':7,'planned_cycle_seconds':72,'actual_cycle_seconds':76.4,'shift_id':'SHIFT-A','status':'RUNNING','created_at':self._now()},
          {'id':'PO-24032','product_sku':'SKU-MOTOR-07','line':'Assembly Line 2','target_qty':600,'good_qty':600,'reject_qty':11,'planned_cycle_seconds':48,'actual_cycle_seconds':49.2,'shift_id':'SHIFT-C','status':'COMPLETED','created_at':self._now()}]
        for m in store.machines(): self.machine_states[m.id]={'asset_id':m.id,'state':'RUNNING' if m.enabled else 'DOWN','reason':'','changed_at':self._now()}
    def create_order(self,b:ProductionOrderCreate,actor:str):
        if b.product_sku not in self.products: raise KeyError('product')
        item={'id':f'PO-{uuid4().hex[:7].upper()}','good_qty':0,'reject_qty':0,'actual_cycle_seconds':b.planned_cycle_seconds,'status':'PLANNED','created_by':actor,'created_at':self._now(),**b.model_dump()}
        with self.lock:self.orders.insert(0,item)
        return item
    def report(self,order_id:str,b:ProductionReport):
        order=next((x for x in self.orders if x['id']==order_id),None)
        if not order:return None
        order.update(b.model_dump()); order['status']='COMPLETED' if order['good_qty']>=order['target_qty'] else 'RUNNING'; order['updated_at']=self._now(); return order
    def set_state(self,asset_id:str,b:MachineStatePatch,actor:str):
        item={'asset_id':asset_id,'state':b.state,'reason':b.reason,'changed_by':actor,'changed_at':self._now()}; self.machine_states[asset_id]=item; return item
    def inspect(self,b:QualityInspectionCreate,actor:str):
        item={'id':f'QI-{uuid4().hex[:8].upper()}','inspector':actor,'created_at':self._now(),**b.model_dump()}; self.inspections.insert(0,item); return item
    def handover(self,b:HandoverCreate,actor:str):
        item={'id':f'HO-{uuid4().hex[:8].upper()}','author':actor,'created_at':self._now(),**b.model_dump()}; self.handovers.insert(0,item); return item
    def andon(self):
        cards=[]
        for m in store.machines():
            st=self.machine_states.get(m.id,{'state':'IDLE','reason':''}); latest=store.latest_for(m.id)
            severity='RED' if st['state'] in ('DOWN','BLOCKED') else 'AMBER' if st['state'] in ('IDLE','CHANGEOVER','STARVED','MAINTENANCE') else 'GREEN'
            if latest and latest.status.value=='CRITICAL':severity='RED'
            cards.append({'asset_id':m.id,'name':m.name,'state':st['state'],'reason':st.get('reason',''),'andon':severity,'temperature':getattr(latest,'temperature',None),'vibration':getattr(latest,'vibration',None)})
        return cards
    def genealogy(self):
        return [{'order_id':o['id'],'product_sku':o['product_sku'],'lot':f"LOT-{o['id'][-5:]}",'line':o['line'],'shift':o['shift_id'],'quality_checks':sum(i['order_id']==o['id'] for i in self.inspections),'traceability':'COMPLETE'} for o in self.orders]
    def executive(self):
        active=[o for o in self.orders if o['status'] in ('PLANNED','RUNNING')]; good=sum(o['good_qty'] for o in self.orders); rejects=sum(o['reject_qty'] for o in self.orders); total=good+rejects
        attainment=sum(min(1,o['good_qty']/max(1,o['target_qty'])) for o in self.orders)/max(1,len(self.orders))*100
        fpq=good/max(1,total)*100
        red=sum(x['andon']=='RED' for x in self.andon())
        return {'active_orders':len(active),'schedule_attainment':round(attainment,1),'first_pass_quality':round(fpq,1),'andon_red':red,'total_good':good,'total_rejects':rejects}
mes=MESOps()
