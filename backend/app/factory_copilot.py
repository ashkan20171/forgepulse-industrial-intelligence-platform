from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from .digital_twin_factory import factory_twin
from .ml_pipeline import anomaly_pipeline
from .autonomous import autonomous
from .flagship import incidents
from .operations import operations
from .mes import mes
from .store import store

class CopilotQuery(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    asset_id: str | None = None

class ApprovalRequest(BaseModel):
    recommendation_id: str
    decision: Literal['APPROVED','REJECTED']
    note: str = Field(default='', max_length=300)

class FactoryCopilot:
    """Grounded, deterministic decision-support layer with an LLM-ready adapter boundary."""
    def __init__(self):
        self._approvals: list[dict] = []

    def _context(self):
        twin=factory_twin.snapshot(); capacity=factory_twin.capacity(); anomalies=anomaly_pipeline.fleet()
        open_inc=[x for x in incidents.list() if x.get('status') not in ('RESOLVED','CLOSED')]
        work=operations.work_orders(); active_wo=[x for x in work if x.get('status')!='CLOSED']
        return twin,capacity,anomalies,open_inc,active_wo

    def recommendations(self):
        twin,cap,anomalies,open_inc,active_wo=self._context(); items=[]
        bottleneck=cap.get('bottleneck')
        if bottleneck and bottleneck.get('utilization_pct',0)>=80:
            items.append(self._rec('CAPACITY','HIGH',f"Relieve {bottleneck['name']} constraint",f"Modeled utilization is {bottleneck['utilization_pct']}% at {bottleneck['capacity_units_per_hour']} units/hour.",'Review routing, micro-stops and staffing before adding upstream capacity.',['factory-twin/capacity']))
        for a in sorted(anomalies,key=lambda x:x['score'],reverse=True)[:3]:
            if a['score']>=.55:
                items.append(self._rec('RELIABILITY','CRITICAL' if a['score']>=.8 else 'HIGH',f"Inspect {a['asset_id']} condition",a['explanation'],'Review RCA evidence and create/confirm a condition-based work order.',['intelligence/anomaly','autonomous/rca'],asset_id=a['asset_id']))
        if twin['quality']<97:
            items.append(self._rec('QUALITY','MEDIUM','Stabilize first-pass quality',f"Modeled quality is {twin['quality']}%.",'Prioritize high-risk production orders and verify recent material/process changes.',['factory-twin/snapshot','factory-twin/predictive-quality']))
        if twin['energy_per_good_unit']>.12:
            items.append(self._rec('ENERGY','MEDIUM','Reduce energy intensity',f"Current estimate is {twin['energy_per_good_unit']} kWh per good unit.",'Target idle losses and bottleneck cycle-time before increasing production speed.',['factory-twin/snapshot']))
        if open_inc:
            items.append(self._rec('INCIDENT','HIGH','Clear open reliability incidents',f"{len(open_inc)} incident(s) remain open.",'Triage by severity and correlate with current anomaly signals.',['incidents','events']))
        return items[:8]

    def _rec(self,category,priority,title,evidence,action,sources,asset_id=None):
        key=f"REC-{abs(hash((category,title,asset_id)))%100000:05d}"
        return {'id':key,'category':category,'priority':priority,'title':title,'evidence':evidence,'recommended_action':action,'asset_id':asset_id,'sources':sources,'requires_human_approval':True}

    def ask(self,body:CopilotQuery):
        q=body.question.lower(); twin,cap,anomalies,open_inc,active_wo=self._context(); sources=[]; confidence=.82
        asset=body.asset_id
        if not asset:
            asset=next((m.id for m in store.machines() if m.id.lower() in q),None)
        if asset:
            insight=next((x for x in anomalies if x['asset_id']==asset),None); rca=autonomous.root_cause(asset); sources=['intelligence/anomaly','autonomous/rca','telemetry/history']
            if insight:
                answer=f"{asset} has an explainable anomaly score of {insight['score']:.0%} with {insight['confidence']:.0%} model confidence. RCA currently points to {rca['primary_cause']} ({rca['confidence']:.0%} confidence)."
                actions=rca['actions'][:3]
            else:
                answer=f"I do not have enough recent telemetry to calculate a reliable condition score for {asset}."; actions=['Collect additional telemetry before making a maintenance decision.'];confidence=.58
        elif any(x in q for x in ('oee','performance','availability','quality','kpi')):
            answer=f"Modeled OEE is {twin['oee']}%: availability {twin['availability']}%, performance {twin['performance']}%, quality {twin['quality']}%. The constraint model identifies {(cap.get('bottleneck') or {}).get('name','no active bottleneck')} as the current capacity focus."
            actions=['Investigate the lowest OEE component first.','Validate modeled losses against shift records before changing the schedule.'];sources=['factory-twin/snapshot','factory-twin/capacity']
        elif any(x in q for x in ('energy','carbon','co2')):
            answer=f"Estimated energy intensity is {twin['energy_per_good_unit']} kWh/good unit and modeled emissions are {twin['carbon_kg_co2e']} kg CO₂e for the current production snapshot."
            actions=['Reduce idle and downtime losses before increasing line speed.','Treat carbon values as estimates until meter and emission-factor integration is validated.'];sources=['factory-twin/snapshot'];confidence=.76
        elif any(x in q for x in ('incident','maintenance','work order','risk')):
            answer=f"There are {len(open_inc)} open incident(s), {len(active_wo)} active work order(s), and {sum(1 for x in anomalies if x['score']>=.7)} asset(s) above the high anomaly threshold."
            actions=['Triage critical anomaly signals against open incidents.','Confirm maintenance actions with the responsible engineer before execution.'];sources=['incidents','work-orders','intelligence/anomaly']
        else:
            recs=self.recommendations(); top=recs[0] if recs else None
            answer='The factory decision layer is currently stable.' if not top else f"The highest-priority grounded recommendation is: {top['title']}. {top['evidence']}"
            actions=[top['recommended_action']] if top else ['Continue monitoring current production and reliability KPIs.'];sources=['decision-intelligence/recommendations'];confidence=.72
        return {'answer':answer,'confidence':confidence,'asset_id':asset,'actions':actions,'sources':sources,'guardrail':'Decision support only. No machine, schedule, maintenance or quality action is executed without human approval.','generated_at':datetime.now(timezone.utc).isoformat()}

    def shift_briefing(self):
        twin,cap,anomalies,open_inc,active_wo=self._context(); high=sorted([x for x in anomalies if x['score']>=.55],key=lambda x:x['score'],reverse=True)
        return {'title':'Shift reliability briefing','generated_at':datetime.now(timezone.utc).isoformat(),'headline':f"OEE {twin['oee']}% · {len(high)} condition risks · {len(open_inc)} open incidents",'bullets':[f"Constraint: {(cap.get('bottleneck') or {}).get('name','none identified')}",f"Active maintenance work orders: {len(active_wo)}",f"Quality: {twin['quality']}% · Energy intensity: {twin['energy_per_good_unit']} kWh/unit"]+[f"Watch {x['asset_id']}: anomaly {x['score']:.0%}" for x in high[:3]],'handover_prompt':'Confirm unresolved alarms, production constraints and maintenance permits with the incoming shift.'}

    def executive_briefing(self):
        twin,cap,anomalies,open_inc,_=self._context(); recs=self.recommendations()
        return {'title':'Executive factory briefing','generated_at':datetime.now(timezone.utc).isoformat(),'scorecard':{'oee':twin['oee'],'quality':twin['quality'],'energy_per_unit':twin['energy_per_good_unit'],'carbon_kg_co2e':twin['carbon_kg_co2e'],'open_incidents':len(open_inc),'high_risk_assets':sum(x['score']>=.7 for x in anomalies)},'narrative':f"Plant effectiveness is {twin['oee']}% with {(cap.get('bottleneck') or {}).get('name','no identified work center')} as the modeled constraint. Decision intelligence surfaced {len(recs)} prioritized improvement opportunities.",'priorities':recs[:3],'caveat':'Energy, carbon and optimization values are modeled estimates and should be validated against plant meters and planning systems before financial decisions.'}

    def approval(self,body:ApprovalRequest,user:str):
        known=next((x for x in self.recommendations() if x['id']==body.recommendation_id),None)
        if not known: return None
        item={'recommendation_id':body.recommendation_id,'decision':body.decision,'note':body.note,'actor':user,'timestamp':datetime.now(timezone.utc).isoformat(),'action_executed':False}
        self._approvals.insert(0,item);return item

    def approvals(self): return self._approvals[:100]

factory_copilot=FactoryCopilot()
