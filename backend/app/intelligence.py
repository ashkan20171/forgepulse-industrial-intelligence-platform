from __future__ import annotations
from datetime import datetime, timezone
from statistics import mean, pstdev
from .store import store


def _trend(values: list[float]) -> float:
    if len(values) < 2: return 0.0
    half=max(1,len(values)//2)
    return round(mean(values[-half:])-mean(values[:half]),3)

def machine_insight(machine_id: str) -> dict | None:
    machine=store.machine(machine_id)
    if not machine: return None
    history=store.history(machine_id, 120)
    if not history:
        return {"machine_id":machine_id,"health_index":100,"failure_risk":0,"confidence":0,"recommendation":"Collect telemetry to establish a condition baseline.","drivers":[],"temperature_trend":0,"vibration_trend":0,"generated_at":datetime.now(timezone.utc)}
    temps=[x.temperature for x in history]; vibes=[x.vibration for x in history]
    latest=history[-1]
    t_margin=max(0,(latest.temperature-machine.temperature_warning)/max(1,machine.temperature_critical-machine.temperature_warning))
    v_margin=max(0,(latest.vibration-machine.vibration_warning)/max(.1,machine.vibration_critical-machine.vibration_warning))
    t_trend=_trend(temps); v_trend=_trend(vibes)
    variability=min(1,(pstdev(temps)/15 if len(temps)>1 else 0)+(pstdev(vibes)/3 if len(vibes)>1 else 0))
    trend_risk=min(1,max(0,t_trend)/12+max(0,v_trend)/2.5)
    risk=min(1,.62*max(t_margin,v_margin)+.23*trend_risk+.15*variability)
    drivers=[]
    if t_margin>.25: drivers.append(f"Temperature is approaching/exceeding the configured limit ({latest.temperature:.1f}°C).")
    if v_margin>.25: drivers.append(f"Vibration is elevated versus the asset baseline ({latest.vibration:.2f} mm/s).")
    if t_trend>2: drivers.append(f"Temperature trend increased by {t_trend:.1f}°C across the observation window.")
    if v_trend>.5: drivers.append(f"Vibration trend increased by {v_trend:.2f} mm/s across the observation window.")
    if not drivers: drivers.append("Signals are stable against configured operating thresholds.")
    pct=round(risk*100,1); health=round(100-pct,1)
    recommendation=("Create an urgent inspection work order and verify the asset locally." if pct>=75 else "Schedule condition-based inspection within the next maintenance window." if pct>=45 else "Continue monitoring; no immediate maintenance intervention indicated.")
    return {"machine_id":machine_id,"health_index":health,"failure_risk":pct,"confidence":round(min(95,35+len(history)*.5),1),"recommendation":recommendation,"drivers":drivers,"temperature_trend":t_trend,"vibration_trend":v_trend,"generated_at":datetime.now(timezone.utc)}

def fleet_insights() -> list[dict]:
    return sorted((machine_insight(m.id) for m in store.machines()),key=lambda x:x["failure_risk"],reverse=True)
