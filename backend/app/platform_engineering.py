from __future__ import annotations
from datetime import datetime, timezone
from threading import RLock

class PlatformEngineering:
    def __init__(self):
        self._lock=RLock()
        self.flags={
            'predictive_quality_v2': {'enabled': False, 'description':'Progressive rollout of the next quality-risk scorer','environments':['staging']},
            'rag_external_llm': {'enabled': False, 'description':'Optional external LLM adapter; local grounded RAG remains default','environments':[]},
            'dynamic_scheduling': {'enabled': True, 'description':'Expose explainable scheduling recommendations','environments':['dev','staging','prod']},
        }
        self.slo={'availability_target':99.9,'latency_p95_ms_target':500,'window_days':30,'availability_observed':99.96,'latency_p95_ms_observed':182}
        self.releases=[{'version':'21.0.0','environment':'staging','strategy':'canary','weight':10,'status':'READY','at':datetime.now(timezone.utc).isoformat()}]
    def overview(self):
        s=self.slo
        allowed=max(0.0,100-s['availability_target'])
        consumed=max(0.0,100-s['availability_observed'])
        budget_remaining=100.0 if allowed==0 else max(0.0,round((1-consumed/allowed)*100,1))
        return {'gitops':'Argo CD','iac':'Terraform foundation','environments':['dev','staging','prod'],'progressive_delivery':['canary','blue-green'],'supply_chain':['SBOM','dependency scan','container scan'],'slo':{**s,'error_budget_remaining_pct':budget_remaining},'release':self.releases[-1]}
    def list_flags(self): return [{'key':k,**v} for k,v in self.flags.items()]
    def set_flag(self,key,enabled):
        with self._lock:
            if key not in self.flags: return None
            self.flags[key]['enabled']=enabled
            return {'key':key,**self.flags[key]}
platform_engineering=PlatformEngineering()
