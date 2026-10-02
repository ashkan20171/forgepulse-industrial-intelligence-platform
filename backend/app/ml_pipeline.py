from __future__ import annotations
from statistics import mean, pstdev
from .store import store

class AnomalyPipeline:
    """Explainable statistical baseline ready to be replaced by an ONNX/MLflow model adapter."""
    def score_asset(self,asset_id:str):
        history=store.history(asset_id,120)
        if not history: return None
        temps=[x.temperature for x in history]; vib=[x.vibration for x in history]; latest=history[-1]
        def z(values,current):
            if len(values)<5:return 0.0
            sd=pstdev(values) or 1.0
            return abs(current-mean(values))/sd
        tz=z(temps,latest.temperature); vz=z(vib,latest.vibration)
        score=min(1.0,max(latest.anomaly_score,min(1.0,max(tz,vz)/4)))
        return {'asset_id':asset_id,'model':'statistical-baseline-v1','score':round(score,3),'confidence':round(min(0.98,0.55+len(history)/300),2),'features':{'temperature_z':round(tz,2),'vibration_z':round(vz,2),'samples':len(history)},'explanation':'Risk combines configured operating thresholds with deviation from the recent asset baseline.'}
    def fleet(self): return [x for m in store.machines() if (x:=self.score_asset(m.id))]
anomaly_pipeline=AnomalyPipeline()
