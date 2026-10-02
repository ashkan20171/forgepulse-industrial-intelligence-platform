from __future__ import annotations
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
import hashlib, hmac, json, urllib.request
from .persistence import IntegrationOutboxRow, WebhookSubscriptionRow, session_scope

class WebhookCreate(BaseModel):
    name: str = Field(min_length=3,max_length=80)
    url: HttpUrl
    events: list[str] = Field(default_factory=lambda:['telemetry.ingested'])
    secret: str = Field(min_length=12,max_length=200)

class ConnectorPatch(BaseModel): enabled: bool|None=None

CONNECTORS=[
 {'id':'sap-erp','name':'SAP ERP / S4HANA','kind':'ERP','protocol':'REST/OData','status':'READY','direction':'BIDIRECTIONAL'},
 {'id':'cmms','name':'Enterprise CMMS','kind':'CMMS','protocol':'REST/Webhook','status':'READY','direction':'BIDIRECTIONAL'},
 {'id':'mes','name':'External MES','kind':'MES','protocol':'REST/Event','status':'READY','direction':'BIDIRECTIONAL'},
 {'id':'opcua','name':'OPC-UA Edge Gateway','kind':'OT','protocol':'OPC-UA','status':'FOUNDATION','direction':'INGRESS'},
]

class IntegrationHub:
    def __init__(self): self.connector_state={x['id']:False for x in CONNECTORS}
    def connectors(self): return [{**x,'enabled':self.connector_state[x['id']]} for x in CONNECTORS]
    def patch_connector(self,cid,enabled):
        if cid not in self.connector_state:return None
        self.connector_state[cid]=enabled; return next({**x,'enabled':enabled} for x in CONNECTORS if x['id']==cid)
    def emit(self,event_type:str,aggregate_id:str,payload:dict):
        row=IntegrationOutboxRow(id=f'EVT-{uuid4().hex[:12].upper()}',event_type=event_type,aggregate_id=aggregate_id,payload=json.dumps(payload,default=str),status='PENDING',attempts=0,created_at=datetime.now(timezone.utc),next_attempt_at=datetime.now(timezone.utc))
        with session_scope() as s:s.add(row)
        return self._out(row)
    def outbox(self,limit=100):
        with session_scope() as s:return [self._out(x) for x in s.scalars(select(IntegrationOutboxRow).order_by(IntegrationOutboxRow.created_at.desc()).limit(limit)).all()]
    def dlq(self):
        with session_scope() as s:return [self._out(x) for x in s.scalars(select(IntegrationOutboxRow).where(IntegrationOutboxRow.status=='DLQ').order_by(IntegrationOutboxRow.created_at.desc())).all()]
    def _out(self,x):return {'id':x.id,'event_type':x.event_type,'aggregate_id':x.aggregate_id,'status':x.status,'attempts':x.attempts,'created_at':x.created_at.isoformat(),'published_at':x.published_at.isoformat() if x.published_at else None,'last_error':x.last_error}
    def webhooks(self):
        with session_scope() as s:return [{'id':x.id,'name':x.name,'url':x.url,'events':json.loads(x.events),'enabled':x.enabled,'created_at':x.created_at.isoformat()} for x in s.scalars(select(WebhookSubscriptionRow).order_by(WebhookSubscriptionRow.created_at.desc())).all()]
    def add_webhook(self,b:WebhookCreate):
        row=WebhookSubscriptionRow(id=f'WH-{uuid4().hex[:8].upper()}',name=b.name,url=str(b.url),events=json.dumps(b.events),secret_hash=hashlib.sha256(b.secret.encode()).hexdigest(),secret=b.secret,enabled=True,created_at=datetime.now(timezone.utc))
        with session_scope() as s:s.add(row)
        return {'id':row.id,'name':row.name,'url':row.url,'events':b.events,'enabled':True,'secret_shown_once':b.secret}
    def deliver_webhooks(self,event):
        with session_scope() as s: hooks=s.scalars(select(WebhookSubscriptionRow).where(WebhookSubscriptionRow.enabled==True)).all()
        body=json.dumps(event,separators=(',',':')).encode()
        failures=[]
        for wh in hooks:
            if event['event_type'] not in json.loads(wh.events) and '*' not in json.loads(wh.events):continue
            sig=hmac.new(wh.secret.encode(),body,hashlib.sha256).hexdigest()
            try:
                req=urllib.request.Request(wh.url,data=body,method='POST',headers={'Content-Type':'application/json','X-IIoT-Signature':'sha256='+sig,'Idempotency-Key':event['id']})
                urllib.request.urlopen(req,timeout=3).read()
            except Exception as exc: failures.append(f'{wh.name}: {exc}')
        return failures
    def dispatch_once(self):
        now=datetime.now(timezone.utc)
        with session_scope() as s:
            rows=s.scalars(select(IntegrationOutboxRow).where(IntegrationOutboxRow.status.in_(['PENDING','RETRY'])).order_by(IntegrationOutboxRow.created_at).limit(25)).all()
            results=[]
            for x in rows:
                if x.next_attempt_at and x.next_attempt_at.replace(tzinfo=timezone.utc)>now:continue
                event={'id':x.id,'event_type':x.event_type,'aggregate_id':x.aggregate_id,'payload':json.loads(x.payload),'occurred_at':x.created_at.isoformat()}
                errors=self.deliver_webhooks(event)
                x.attempts+=1
                if errors:
                    x.last_error='; '.join(errors)[:1000]
                    if x.attempts>=5:x.status='DLQ'
                    else:x.status='RETRY';x.next_attempt_at=now+timedelta(seconds=min(300,2**x.attempts))
                else:x.status='PUBLISHED';x.published_at=now;x.last_error=None
                results.append(self._out(x))
            return results
    def retry_dlq(self,event_id):
        with session_scope() as s:
            x=s.get(IntegrationOutboxRow,event_id)
            if not x or x.status!='DLQ':return None
            x.status='PENDING';x.attempts=0;x.last_error=None;x.next_attempt_at=datetime.now(timezone.utc);s.flush();return self._out(x)
    def status(self):
        items=self.outbox(500)
        return {'outbox_pending':sum(x['status'] in ('PENDING','RETRY') for x in items),'published':sum(x['status']=='PUBLISHED' for x in items),'dlq':sum(x['status']=='DLQ' for x in items),'webhooks':len(self.webhooks()),'connectors_enabled':sum(self.connector_state.values()),'delivery_semantics':'at-least-once','idempotency':'Idempotency-Key = outbox event id'}

integration_hub=IntegrationHub()
