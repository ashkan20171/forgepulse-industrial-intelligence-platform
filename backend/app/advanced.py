from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from .store import store
from .operations import operations
from .intelligence import machine_insight

class AlarmRule(BaseModel):
    id: str
    name: str
    metric: str
    operator: str = ">="
    threshold: float
    severity: str = "WARNING"
    enabled: bool = True

class AlarmRulePatch(BaseModel):
    threshold: float | None = None
    severity: str | None = None
    enabled: bool | None = None

_RULES = {
    "temperature-warning": AlarmRule(id="temperature-warning", name="High temperature", metric="temperature", threshold=75, severity="WARNING"),
    "vibration-critical": AlarmRule(id="vibration-critical", name="Critical vibration", metric="vibration", threshold=7.1, severity="CRITICAL"),
}

def alarm_rules(): return list(_RULES.values())
def patch_alarm_rule(rule_id: str, patch: AlarmRulePatch):
    current = _RULES.get(rule_id)
    if not current: return None
    updated = current.model_copy(update=patch.model_dump(exclude_none=True))
    _RULES[rule_id] = updated
    return updated

def asset_detail(machine_id: str):
    machine = store.machine(machine_id)
    if not machine: return None
    history = store.history(machine_id, 120)
    insight = machine_insight(machine_id)
    return {
        "asset": machine,
        "latest": history[-1] if history else None,
        "history": history,
        "insight": insight,
        "alerts": [a for a in store.alerts() if a.machine_id == machine_id][:20],
        "work_orders": [w for w in operations.work_orders() if w.asset_id == machine_id],
    }

def maintenance_calendar():
    result=[]
    for w in operations.work_orders():
        stamp = getattr(w, "created_at", None) or datetime.now(timezone.utc)
        result.append({"id":w.id,"asset_id":w.asset_id,"title":w.title,"priority":w.priority,"status":w.status,"date":stamp})
    return result

def copilot(machine_id: str):
    detail=asset_detail(machine_id)
    if not detail: return None
    insight=detail["insight"]
    open_orders=sum(getattr(w,"status","")=="OPEN" for w in detail["work_orders"])
    alerts=sum(not a.acknowledged for a in detail["alerts"])
    if not insight:
        summary="Telemetry is not yet sufficient for a condition assessment."
        actions=["Verify sensor connectivity", "Collect a stable telemetry window", "Confirm operating thresholds"]
    else:
        summary=f"{machine_id} has a health index of {insight['health_index']} with {insight['failure_risk']}% condition risk. {insight['recommendation']}"
        actions=list(insight.get("drivers", []))[:2] + (["Review open maintenance work"] if open_orders else ["Continue condition monitoring"])
    return {"asset_id":machine_id,"summary":summary,"actions":actions,"open_work_orders":open_orders,"unacknowledged_alerts":alerts,"generated_at":datetime.now(timezone.utc)}
