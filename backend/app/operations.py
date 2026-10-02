from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field
from sqlalchemy import select
from .persistence import WorkOrderRow, AuditRow, session_scope
class WorkOrderCreate(BaseModel):
    asset_id:str=Field(min_length=1,max_length=80); title:str=Field(min_length=3,max_length=140); priority:str=Field(default='MEDIUM',pattern=r'^(LOW|MEDIUM|HIGH|CRITICAL)$'); assignee:str=Field(default='Unassigned',max_length=100)
class WorkOrder(BaseModel):
    id:str; asset_id:str; title:str; priority:str; assignee:str; status:str='OPEN'; created_at:datetime; completed_at:datetime|None=None
class AuditEvent(BaseModel): id:str; actor:str; action:str; resource:str; timestamp:datetime
def _wo(r): return WorkOrder(id=r.id,asset_id=r.asset_id,title=r.title,priority=r.priority,assignee=r.assignee,status=r.status,created_at=r.created_at,completed_at=r.completed_at)
class OperationsStore:
    def work_orders(self):
        with session_scope() as s:return [_wo(x) for x in s.scalars(select(WorkOrderRow).order_by(WorkOrderRow.created_at.desc())).all()]
    def create_work_order(self,data,actor='operator'):
        item=WorkOrderRow(id=f"WO-{uuid4().hex[:8].upper()}",**data.model_dump(),status='OPEN',created_at=datetime.now(timezone.utc))
        with session_scope() as s:s.add(item)
        self.audit(actor,'CREATE_WORK_ORDER',item.id); return _wo(item)
    def close_work_order(self,wid,actor='operator'):
        with session_scope() as s:
            item=s.get(WorkOrderRow,wid)
            if not item:return None
            item.status='COMPLETED'; item.completed_at=datetime.now(timezone.utc); s.flush(); result=_wo(item)
        self.audit(actor,'CLOSE_WORK_ORDER',wid); return result
    def audit(self,actor,action,resource):
        row=AuditRow(id=str(uuid4()),actor=actor,action=action,resource=resource,timestamp=datetime.now(timezone.utc))
        with session_scope() as s:s.add(row)
        return AuditEvent.model_validate(row,from_attributes=True)
    def audit_log(self):
        with session_scope() as s:return [AuditEvent.model_validate(x,from_attributes=True) for x in s.scalars(select(AuditRow).order_by(AuditRow.timestamp.desc()).limit(500)).all()]
operations=OperationsStore()
