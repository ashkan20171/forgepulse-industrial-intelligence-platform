from __future__ import annotations
from datetime import datetime, timezone
import csv, io, json
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from .analytics import build_analytics
from .operations import operations
from .store import store
from .persistence import SettingRow, session_scope
from sqlalchemy import select

class PlatformSettingsPatch(BaseModel):
    site_name: str | None = Field(default=None, min_length=2, max_length=80)
    timezone: str | None = Field(default=None, min_length=2, max_length=50)
    retention_days: int | None = Field(default=None, ge=7, le=3650)
    maintenance_window: str | None = Field(default=None, max_length=80)

_DEFAULT_SETTINGS = {"site_name":"Plant Alpha","timezone":"UTC","retention_days":365,"maintenance_window":"Sunday 02:00–04:00"}
def platform_settings():
    result=dict(_DEFAULT_SETTINGS)
    with session_scope() as s:
        for row in s.scalars(select(SettingRow)).all():
            try: result[row.key]=json.loads(row.value)
            except Exception: result[row.key]=row.value
    return result
def patch_platform_settings(body: PlatformSettingsPatch):
    values=body.model_dump(exclude_none=True)
    with session_scope() as s:
        for key,value in values.items():
            row=s.get(SettingRow,key)
            if row: row.value=json.dumps(value)
            else: s.add(SettingRow(key=key,value=json.dumps(value)))
    return platform_settings()

def kpi_trends():
    analytics = build_analytics()
    latest = store.latest()
    base = max(1, len(latest))
    points=[]
    for i in range(12):
        drift=(i-5.5)*0.35
        anomaly=sum(x.anomaly_score for x in latest)/base if latest else 0
        points.append({"period":f"T-{11-i}","availability":round(max(0,99.1-drift-anomaly),1),"performance":round(max(0,94.8-drift*0.5-anomaly*4),1),"quality":round(max(0,98.6-anomaly*2),1)})
    return {"series":points,"snapshot":analytics}

def telemetry_csv():
    buf=io.StringIO(); writer=csv.writer(buf); writer.writerow(["machine_id","temperature","vibration","status","anomaly_score","timestamp"])
    for item in store.latest(): writer.writerow([item.machine_id,item.temperature,item.vibration,item.status.value,item.anomaly_score,item.timestamp.isoformat()])
    return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=telemetry-export.csv"})

def backup_snapshot():
    return {"schema":"ashkan-iot-backup/v1","created_at":datetime.now(timezone.utc).isoformat(),"machines":[x.model_dump(mode="json") for x in store.machines()],"latest":[x.model_dump(mode="json") for x in store.latest()],"work_orders":[x.model_dump(mode="json") for x in operations.work_orders()],"settings":platform_settings()}

def metrics_text():
    latest=store.latest(); alerts=store.alerts(); work=operations.work_orders()
    lines=["# HELP ashkan_iot_assets Number of configured industrial assets","# TYPE ashkan_iot_assets gauge",f"ashkan_iot_assets {len(store.machines())}","# HELP ashkan_iot_critical_assets Assets currently reporting critical status","# TYPE ashkan_iot_critical_assets gauge",f'ashkan_iot_critical_assets {sum(x.status.value=="CRITICAL" for x in latest)}',"# HELP ashkan_iot_unacknowledged_alerts Open alerts","# TYPE ashkan_iot_unacknowledged_alerts gauge",f"ashkan_iot_unacknowledged_alerts {sum(not x.acknowledged for x in alerts)}",f"ashkan_iot_open_work_orders {sum(x.status=='OPEN' for x in work)}"]
    return "\n".join(lines)+"\n"
