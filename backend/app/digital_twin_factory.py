from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from .mes import mes
from .advanced_mes import advanced_mes
from .store import store

class ScenarioRequest(BaseModel):
    demand_multiplier: float = Field(default=1.0, ge=.5, le=2.0)
    speed_improvement_pct: float = Field(default=0, ge=0, le=30)
    downtime_reduction_pct: float = Field(default=0, ge=0, le=80)
    quality_improvement_pct: float = Field(default=0, ge=0, le=10)

class FactoryTwin:
    """Explainable planning twin. Deterministic formulas keep portfolio claims auditable."""
    emission_factor_kg_per_kwh = .38

    def snapshot(self):
        orders=mes.orders
        planned=sum(o['target_qty']*o['planned_cycle_seconds'] for o in orders)/3600
        actual=sum(max(1,o['good_qty']+o['reject_qty'])*o['actual_cycle_seconds'] for o in orders)/3600
        good=sum(o['good_qty'] for o in orders); reject=sum(o['reject_qty'] for o in orders)
        assets=store.machines(); enabled=sum(m.enabled for m in assets)
        availability=enabled/max(1,len(assets))*100
        quality=good/max(1,good+reject)*100
        performance=min(100, planned/max(1,actual)*100)
        oee=availability*performance*quality/10000
        energy_kwh=round(actual*18.5,1)
        return {'generated_at':datetime.now(timezone.utc).isoformat(),'oee':round(oee,1),'availability':round(availability,1),'performance':round(performance,1),'quality':round(quality,1),'throughput_good':good,'energy_kwh':energy_kwh,'energy_per_good_unit':round(energy_kwh/max(1,good),3),'carbon_kg_co2e':round(energy_kwh*self.emission_factor_kg_per_kwh,1)}

    def capacity(self):
        rows=[]
        routing=advanced_mes.routing
        for wc in advanced_mes.work_centers:
            ops=[x for x in routing if x['work_center']==wc['id']]
            cycle=max([x['cycle_seconds'] for x in ops] or [60])
            theoretical=round(3600/cycle,1); effective=round(theoretical*wc['efficiency']/100,1)
            rows.append({'work_center':wc['id'],'name':wc['name'],'cycle_seconds':cycle,'efficiency':wc['efficiency'],'capacity_units_per_hour':effective,'utilization_pct':round(min(99,68+(100-wc['efficiency'])*1.8),1)})
        bottleneck=max(rows,key=lambda x:x['utilization_pct']) if rows else None
        return {'work_centers':rows,'bottleneck':bottleneck,'constraint_reason':'Highest modeled utilization; improve this station before adding upstream capacity.' if bottleneck else ''}

    def scenario(self,b:ScenarioRequest):
        base=self.snapshot(); cap=self.capacity(); constraint=(cap['bottleneck'] or {}).get('utilization_pct',0)
        demand_pressure=max(0,(b.demand_multiplier-1)*35)
        perf=min(100,base['performance']+b.speed_improvement_pct*.65+b.downtime_reduction_pct*.18-demand_pressure)
        avail=min(100,base['availability']+b.downtime_reduction_pct*.22)
        quality=min(100,base['quality']+b.quality_improvement_pct)
        oee=avail*perf*quality/10000
        throughput=round(base['throughput_good']*b.demand_multiplier*(oee/max(1,base['oee'])))
        energy_per=max(.01,base['energy_per_good_unit']*(1-b.speed_improvement_pct/250)*(1-b.downtime_reduction_pct/400))
        return {'baseline_oee':base['oee'],'projected_oee':round(oee,1),'projected_good_units':throughput,'projected_energy_per_unit':round(energy_per,3),'projected_carbon_kg_co2e':round(throughput*energy_per*self.emission_factor_kg_per_kwh,1),'constraint_risk':'HIGH' if constraint+demand_pressure>95 else 'MEDIUM' if constraint+demand_pressure>82 else 'LOW','assumptions':b.model_dump(),'explanation':['OEE is recomputed from availability × performance × quality.','Demand pressure reduces modeled performance when the current constraint is highly utilized.','Energy/unit improves conservatively with speed and downtime improvements.']}

    def conflicts(self):
        now=datetime.now(timezone.utc)
        out=[]
        for o in mes.orders:
            if o['status']!='RUNNING': continue
            for m in store.machines():
                if not m.enabled:
                    out.append({'severity':'HIGH','production_order':o['id'],'asset_id':m.id,'type':'MAINTENANCE_PRODUCTION_CONFLICT','message':f'{m.name} is unavailable while {o["id"]} is running.','detected_at':now.isoformat(),'recommendation':'Reschedule the order or return the asset to a validated operating state.'})
        return out

    def predictive_quality(self):
        result=[]
        for o in mes.orders:
            total=o['good_qty']+o['reject_qty']; reject_rate=o['reject_qty']/max(1,total)*100
            cycle_delta=max(0,o['actual_cycle_seconds']/o['planned_cycle_seconds']-1)*100
            risk=min(99,reject_rate*5+cycle_delta*1.4)
            result.append({'order_id':o['id'],'sku':o['product_sku'],'quality_risk':round(risk,1),'predicted_fpq':round(max(0,100-risk*.35),1),'drivers':[f'reject rate {reject_rate:.1f}%',f'cycle deviation +{cycle_delta:.1f}%'],'recommendation':'Inspect process settings and recent material lots.' if risk>=20 else 'Continue standard sampling plan.'})
        return result
factory_twin=FactoryTwin()
