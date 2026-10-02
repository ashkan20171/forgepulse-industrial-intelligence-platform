from datetime import datetime,timezone,timedelta
from uuid import uuid4
from pydantic import BaseModel,Field
from .mes import mes
class ConsumptionCreate(BaseModel): order_id:str; component_sku:str; quantity:float=Field(gt=0); lot:str=Field(min_length=2,max_length=80)
class NCRCreate(BaseModel): order_id:str; defect:str=Field(min_length=3,max_length=200); severity:str=Field(pattern=r'^(LOW|MEDIUM|HIGH|CRITICAL)$'); disposition:str='REVIEW'
class CAPAPatch(BaseModel): action:str=Field(min_length=3,max_length=300); owner:str=Field(min_length=2,max_length=80); status:str=Field(pattern=r'^(OPEN|IN_PROGRESS|VERIFIED|CLOSED)$')
class AdvancedMES:
 def __init__(self):
  self.work_centers=[{'id':'WC-ASM-01','name':'Assembly Cell 1','efficiency':94.2},{'id':'WC-ASM-02','name':'Assembly Cell 2','efficiency':91.8},{'id':'WC-QA-01','name':'Quality Gate','efficiency':97.1}]
  self.bom=[{'product_sku':'SKU-PUMP-01','component_sku':'CMP-BRG-6205','description':'Precision bearing','qty_per':2,'unit':'pcs'},{'product_sku':'SKU-PUMP-01','component_sku':'CMP-SEAL-22','description':'Mechanical seal','qty_per':1,'unit':'pcs'}]
  self.routing=[{'product_sku':'SKU-PUMP-01','operation_no':10,'name':'Housing assembly','work_center':'WC-ASM-01','cycle_seconds':42},{'product_sku':'SKU-PUMP-01','operation_no':20,'name':'Final assembly','work_center':'WC-ASM-02','cycle_seconds':30},{'product_sku':'SKU-PUMP-01','operation_no':30,'name':'Pressure test','work_center':'WC-QA-01','cycle_seconds':24}]
  self.consumption=[]; self.ncr=[]; self.instructions=[{'id':'WI-PUMP-01','product_sku':'SKU-PUMP-01','revision':'D','title':'Pump final assembly','steps':['Verify component lot','Torque housing bolts to 42 Nm','Run leak test at 8 bar','Record serial and inspection'],'approved':True}]
 def now(self):return datetime.now(timezone.utc).isoformat()
 def schedule(self):
  base=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0); out=[]
  for i,o in enumerate(mes.orders):
   start=base+timedelta(hours=i*3); hours=max(1,min(8,o['target_qty']*o['planned_cycle_seconds']/3600)); out.append({'order_id':o['id'],'sku':o['product_sku'],'line':o['line'],'start':start.isoformat(),'end':(start+timedelta(hours=hours)).isoformat(),'progress':round(min(100,o['good_qty']/max(1,o['target_qty'])*100),1),'status':o['status']})
  return out
 def wip(self):return [{'order_id':o['id'],'sku':o['product_sku'],'completed':o['good_qty']+o['reject_qty'],'remaining':max(0,o['target_qty']-o['good_qty']-o['reject_qty']),'stage':'FINAL_ASSEMBLY' if o['status']=='RUNNING' else o['status']} for o in mes.orders]
 def consume(self,b,actor):
  if not any(o['id']==b.order_id for o in mes.orders):return None
  x={'id':'MC-'+uuid4().hex[:8].upper(),'actor':actor,'timestamp':self.now(),**b.model_dump()};self.consumption.insert(0,x);return x
 def create_ncr(self,b,actor):
  x={'id':'NCR-'+uuid4().hex[:7].upper(),'created_by':actor,'created_at':self.now(),'capa':None,**b.model_dump()};self.ncr.insert(0,x);return x
 def capa(self,nid,b):
  x=next((n for n in self.ncr if n['id']==nid),None)
  if x:x['capa']={**b.model_dump(),'updated_at':self.now()}
  return x
 def spc(self):
  v=[76.4,73.1,74,75.2,72.9,77,74.8,75.1,73.9,74.4];m=sum(v)/len(v);r=max(v)-min(v);return {'metric':'cycle_time_seconds','samples':v,'mean':round(m,2),'ucl':round(m+r*.55,2),'lcl':round(m-r*.55,2),'process_status':'IN_CONTROL'}
 def costs(self):
  out=[]
  for o in mes.orders:
   mat=o['target_qty']*18.5;lab=(o['good_qty']+o['reject_qty'])*o['actual_cycle_seconds']/3600*32;scr=o['reject_qty']*24;t=mat+lab+scr;out.append({'order_id':o['id'],'sku':o['product_sku'],'material':round(mat,2),'labor':round(lab,2),'scrap':round(scr,2),'total':round(t,2),'unit_cost':round(t/max(1,o['good_qty']),2)})
  return out
advanced_mes=AdvancedMES()
