from __future__ import annotations
from dataclasses import dataclass, asdict
from uuid import uuid4
from .event_engine import event_bus
@dataclass
class Rule: id:str; name:str; metric:str; operator:str; threshold:float; severity:str; enabled:bool=True
class RuleEngine:
    def __init__(self):self.rules=[Rule('temp-critical','Critical temperature','temperature','>=',85,'CRITICAL'),Rule('vibration-high','High vibration','vibration','>=',7,'CRITICAL'),Rule('temp-warning','Temperature warning','temperature','>=',75,'WARNING')]
    def list(self):return [asdict(x) for x in self.rules]
    def create(self,b):
        r=Rule('rule-'+uuid4().hex[:8],b.name,b.metric,b.operator,b.threshold,b.severity,b.enabled);self.rules.append(r);return asdict(r)
    def delete(self,rid):
        before=len(self.rules);self.rules=[x for x in self.rules if x.id!=rid];return len(self.rules)<before
    def evaluate(self,t):
        fired=[]
        for r in self.rules:
            if not r.enabled:continue
            v=getattr(t,r.metric,None)
            if v is None:continue
            matched={'>=':v>=r.threshold,'>':v>r.threshold,'<=':v<=r.threshold,'<':v<r.threshold}[r.operator]
            if matched:fired.append(event_bus.publish('RULE_TRIGGERED',t.machine_id,r.severity,f'{r.name}: {v}',{'rule_id':r.id,'metric':r.metric,'value':v,'threshold':r.threshold}))
        return fired
rule_engine=RuleEngine()
