from __future__ import annotations
import math, re, uuid
from collections import Counter
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=3,max_length=120)
    kind: str = Field(default='SOP',max_length=30)
    asset_id: str|None=None
    content: str = Field(min_length=20,max_length=12000)
    tags: list[str] = Field(default_factory=list,max_length=12)

class RagQuery(BaseModel):
    question: str = Field(min_length=3,max_length=600)
    asset_id: str|None=None
    conversation_id: str|None=None

class KnowledgeRAG:
    def __init__(self):
        self.docs=[]; self.history={}; self.usage=[]
        self._seed()
    def _seed(self):
        seeds=[
          ('SOP-ROTATING-001','Rotating equipment vibration response','SOP','M-1001','When vibration exceeds the warning threshold, verify sensor mounting, inspect bearing temperature, check lubrication condition and review recent load changes. Do not restart equipment after a critical trip until a qualified technician completes the safety and mechanical inspection.',['vibration','bearing','safety']),
          ('MANUAL-PUMP-014','Centrifugal pump condition guide','MANUAL','M-1002','High vibration combined with rising temperature can indicate bearing degradation, cavitation, misalignment or coupling wear. Compare suction conditions and process load before assigning root cause. Isolate energy before intrusive inspection.',['pump','cavitation','alignment']),
          ('SOP-HANDOVER-003','Shift handover reliability checklist','SOP',None,'Incoming shifts must review unresolved alarms, open incidents, active work orders, maintenance permits, quality holds and constrained work centers. Record ownership and the next safe action for each unresolved item.',['handover','incident','maintenance']),
          ('POL-AI-001','AI decision-support governance','POLICY',None,'AI and analytics outputs are advisory. Operators must validate evidence, follow approved procedures and obtain required authorization before machine, maintenance, production schedule or quality disposition actions.',['ai','governance','approval'])]
        for doc_id,title,kind,asset,content,tags in seeds:self.docs.append({'id':doc_id,'title':title,'kind':kind,'asset_id':asset,'content':content,'tags':tags,'version':'1.0','status':'APPROVED','updated_at':datetime.now(timezone.utc).isoformat()})
    def _tokens(self,s): return re.findall(r"[a-z0-9]+",s.lower())
    def _score(self,q,d):
        qv=Counter(self._tokens(q)); dv=Counter(self._tokens(d['title']+' '+d['content']+' '+' '.join(d['tags'])))
        dot=sum(qv[k]*dv[k] for k in qv); nq=math.sqrt(sum(v*v for v in qv.values())); nd=math.sqrt(sum(v*v for v in dv.values()))
        return dot/(nq*nd) if nq and nd else 0
    def search(self,q,asset_id=None,limit=4):
        rows=[]
        for d in self.docs:
            score=self._score(q,d)+(0.12 if asset_id and d.get('asset_id')==asset_id else 0)
            if score>0: rows.append({**d,'score':round(min(score,1),3),'excerpt':d['content'][:240]})
        return sorted(rows,key=lambda x:x['score'],reverse=True)[:limit]
    def add(self,b,actor):
        item={'id':'KB-'+uuid.uuid4().hex[:8].upper(),'title':b.title,'kind':b.kind.upper(),'asset_id':b.asset_id,'content':b.content,'tags':b.tags,'version':'1.0','status':'APPROVED','updated_at':datetime.now(timezone.utc).isoformat(),'created_by':actor};self.docs.insert(0,item);return item
    def guard(self,q):
        patterns=['ignore previous','ignore all instructions','reveal system prompt','show secret','auth_secret','password','bypass guard','disable safety']
        hits=[x for x in patterns if x in q.lower()]
        return {'allowed':not hits,'risk':'HIGH' if hits else 'LOW','signals':hits,'message':'Potential prompt-injection or secret-exfiltration request blocked.' if hits else 'No injection pattern detected.'}
    def record(self,conversation_id,user,question,response):
        cid=conversation_id or 'C-'+uuid.uuid4().hex[:10].upper(); item={'id':uuid.uuid4().hex[:10],'conversation_id':cid,'user':user,'question':question,'response':response,'timestamp':datetime.now(timezone.utc).isoformat()};self.history.setdefault(cid,[]).append(item);self.usage.insert(0,{'timestamp':item['timestamp'],'user':user,'conversation_id':cid,'citations':len(response.get('citations',[])),'confidence':response.get('confidence',0),'blocked':response.get('blocked',False)});return cid
    def governance(self):
        total=len(self.usage); blocked=sum(x['blocked'] for x in self.usage); cited=sum(x['citations']>0 for x in self.usage)
        return {'queries':total,'blocked_queries':blocked,'citation_coverage_pct':round(cited/max(1,total)*100,1),'knowledge_documents':len(self.docs),'mode':'LOCAL_GROUNDED','external_llm_enabled':False,'policy':'Human approval required for operational actions.'}
knowledge_rag=KnowledgeRAG()
