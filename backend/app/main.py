import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .analytics import build_analytics
from .auth import LoginRequest, RefreshRequest, UserCreate, UserPatch, UserInfo, authenticate, create_token_pair, refresh_tokens, revoke_refresh, current_user, users, user_from_access_token
from .config import settings
from .database import db_manager
from .models import MachinePatch, TelemetryIn
from .mqtt_client import mqtt_service
from .operations import WorkOrderCreate, operations
from .intelligence import fleet_insights, machine_insight
from .devices import DevicePatch, devices
from .notifications import notifications
from .store import store
from .advanced import AlarmRulePatch, alarm_rules, patch_alarm_rule, asset_detail, maintenance_calendar, copilot
from .enterprise import PlatformSettingsPatch, platform_settings, patch_platform_settings, kpi_trends, telemetry_csv, backup_snapshot, metrics_text
from .flagship import IncidentCreate, ApiKeyCreate, incidents, api_keys, hierarchy, reliability_kpis, limiter
from .persistence import init_database, ping as postgres_ping
from .distributed import redis_ping
from .observability import configure_observability
from .event_engine import event_bus
from .rule_engine import rule_engine
from .ml_pipeline import anomaly_pipeline
from .autonomous import autonomous, RuleCreate
from .manufacturing import manufacturing, DowntimeCreate, SparePartCreate, RcaReview
from .mes import mes, ProductionOrderCreate, ProductionReport, QualityInspectionCreate, MachineStatePatch, HandoverCreate
from .advanced_mes import advanced_mes, ConsumptionCreate, NCRCreate, CAPAPatch
from .digital_twin_factory import factory_twin, ScenarioRequest
from .factory_copilot import factory_copilot, CopilotQuery, ApprovalRequest
from .knowledge_rag import knowledge_rag, KnowledgeDocumentCreate, RagQuery
from .security_zero_trust import security, MfaVerify, generate_totp_secret, verify_totp, recovery_codes, PERMISSION_CATALOG, password_policy
from .integration_hub import integration_hub, WebhookCreate, ConnectorPatch
from .cloud_native import runtime, liveness, readiness, startup, begin_drain, request_started, request_finished, postgres_circuit, redis_circuit
from .platform_engineering import platform_engineering

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    users.seed()
    mqtt_service.start()
    logger.info("%s %s started", settings.APP_NAME, settings.APP_VERSION)
    yield
    begin_drain()
    deadline = asyncio.get_event_loop().time() + settings.SHUTDOWN_GRACE_SECONDS
    while runtime.inflight_requests and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
    mqtt_service.stop()
    db_manager.close()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Industrial telemetry, condition monitoring and maintenance operations API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
configure_observability(app)

STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if runtime.shutting_down and request.url.path not in {"/health/live", "/health/ready", "/health/startup"}:
        return JSONResponse({"detail": "Instance is draining"}, status_code=503, headers={"Connection": "close"})
    request_started()
    try:
        if request.url.path.startswith("/api/"):
            key = request.client.host if request.client else "unknown"
            if not limiter.allow(key):
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail":"Rate limit exceeded"}, status_code=429, headers={"Retry-After":"60"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
    finally:
        request_finished()

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC / "index.html")

@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request):
    ip=request.client.host if request.client else "unknown"
    if security.is_locked(body.username): raise HTTPException(423, "Account temporarily locked after repeated failed attempts")
    user = authenticate(body.username, body.password)
    if not user:
        security.failed(body.username,ip); raise HTTPException(401, "Invalid username or password")
    security.success(user.username,ip); operations.audit(user.username, "LOGIN", "session")
    return {**create_token_pair(user.username), "user": user, "mfa_enrolled": bool(security.mfa.get(user.username,{}).get("enabled"))}

@app.get("/api/auth/me")
def me(user: UserInfo = Depends(current_user)):
    return user

@app.post("/api/auth/refresh")
def refresh(body: RefreshRequest):
    return refresh_tokens(body.refresh_token)

@app.post("/api/auth/logout", status_code=204)
def logout(body: RefreshRequest):
    revoke_refresh(body.refresh_token)

@app.get("/api/users")
def list_users(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    return users.list()

@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    created = users.create(body); operations.audit(user.username, "CREATE_USER", created.username); return created

@app.patch("/api/users/{username}")
def patch_user(username: str, body: UserPatch, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    if username == user.username and body.enabled is False: raise HTTPException(409, "Cannot disable your active account")
    item = users.patch(username, body)
    if not item: raise HTTPException(404, "User not found")
    operations.audit(user.username, "UPDATE_USER", username); return item


@app.get("/health/live", include_in_schema=False)
def health_live():
    return liveness()

@app.get("/health/ready", include_in_schema=False)
def health_ready():
    ok, payload = readiness()
    return JSONResponse(payload, status_code=200 if ok else 503)

@app.get("/health/startup", include_in_schema=False)
def health_startup():
    ok, payload = startup()
    return JSONResponse(payload, status_code=200 if ok else 503)

@app.get("/api/platform/runtime")
def platform_runtime(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    return {**runtime.snapshot(), "circuits": [postgres_circuit.state(), redis_circuit.state()]}


@app.get("/api/platform-engineering/overview")
def platform_engineering_overview(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    return platform_engineering.overview()

@app.get("/api/platform-engineering/flags")
def platform_feature_flags(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    return platform_engineering.list_flags()

@app.patch("/api/platform-engineering/flags/{key}")
def patch_platform_feature_flag(key: str, enabled: bool, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    item=platform_engineering.set_flag(key, enabled)
    if not item: raise HTTPException(404, "Feature flag not found")
    operations.audit(user.username, "FEATURE_FLAG", key)
    return item

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "mqtt_connected": mqtt_service.connected,
        "influxdb_connected": db_manager.ping(),
        "environment": settings.ENVIRONMENT,
        "postgres_connected": postgres_ping(),
        "redis_connected": redis_ping(),
    }

@app.get("/api/machines")
def machines():
    return store.machines()

@app.patch("/api/machines/{machine_id}")
def patch_machine(machine_id: str, patch: MachinePatch, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Read-only role")
    item = store.update_machine(machine_id, **patch.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(404, "Machine not found")
    operations.audit(user.username, "UPDATE_ASSET", machine_id)
    return item

@app.get("/api/telemetry/latest")
def latest():
    return store.latest()

@app.get("/api/telemetry/{machine_id}")
def history(machine_id: str, limit: int = Query(100, ge=1, le=500)):
    if not store.machine(machine_id):
        raise HTTPException(404, "Machine not found")
    return store.history(machine_id, limit)

@app.post("/api/telemetry", status_code=201)
def ingest(metric: TelemetryIn):
    saved = store.ingest(metric)
    if saved is None:
        raise HTTPException(409, "Machine is disabled")
    db_manager.write(saved)
    integration_hub.emit("telemetry.ingested", saved.machine_id, saved.model_dump())
    devices.sync(saved.machine_id)
    fired = rule_engine.evaluate(saved)
    if saved.anomaly_score >= 0.7:
        event_bus.publish("ANOMALY_DETECTED", saved.machine_id, saved.status.value, f"Anomaly score {saved.anomaly_score:.0%}", {"score": saved.anomaly_score})
    if saved.status.value == "CRITICAL":
        notifications.push("Critical condition", f"{saved.machine_id} requires immediate attention.", "CRITICAL")
    return saved

@app.get("/api/alerts")
def alerts():
    return store.alerts()

@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Read-only role")
    item = store.acknowledge(alert_id)
    if not item:
        raise HTTPException(404, "Alert not found")
    operations.audit(user.username, "ACK_ALERT", alert_id)
    return item

@app.get("/api/work-orders")
def work_orders():
    return operations.work_orders()

@app.post("/api/work-orders", status_code=201)
def create_work_order(body: WorkOrderCreate, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Read-only role")
    if not store.machine(body.asset_id):
        raise HTTPException(404, "Asset not found")
    return operations.create_work_order(body, user.username)

@app.post("/api/work-orders/{work_order_id}/close")
def close_work_order(work_order_id: str, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER":
        raise HTTPException(403, "Read-only role")
    item = operations.close_work_order(work_order_id, user.username)
    if not item:
        raise HTTPException(404, "Work order not found")
    return item

@app.get("/api/audit")
def audit(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "Admin role required")
    return operations.audit_log()


@app.get("/api/intelligence")
def intelligence(): return fleet_insights()

@app.get("/api/intelligence/{machine_id}")
def intelligence_machine(machine_id: str):
    item=machine_insight(machine_id)
    if not item: raise HTTPException(404, "Machine not found")
    return item

@app.get("/api/devices")
def device_registry(): return devices.list()

@app.patch("/api/devices/{asset_id}")
def patch_device(asset_id: str, patch: DevicePatch, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    item=devices.patch(asset_id, **patch.model_dump(exclude_none=True))
    if not item: raise HTTPException(404, "Device not found")
    operations.audit(user.username, "UPDATE_DEVICE_TWIN", asset_id)
    return item

@app.get("/api/notifications")
def notification_list(user: UserInfo = Depends(current_user)): return notifications.list()

@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: UserInfo = Depends(current_user)):
    item=notifications.read(notification_id)
    if not item: raise HTTPException(404, "Notification not found")
    return item


@app.get("/api/assets/{machine_id}/detail")
def get_asset_detail(machine_id: str):
    item = asset_detail(machine_id)
    if not item: raise HTTPException(404, "Asset not found")
    return item

@app.get("/api/maintenance/calendar")
def get_maintenance_calendar(user: UserInfo = Depends(current_user)):
    return maintenance_calendar()

@app.get("/api/alarm-rules")
def get_alarm_rules(user: UserInfo = Depends(current_user)):
    return alarm_rules()

@app.patch("/api/alarm-rules/{rule_id}")
def update_alarm_rule(rule_id: str, patch: AlarmRulePatch, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    item = patch_alarm_rule(rule_id, patch)
    if not item: raise HTTPException(404, "Rule not found")
    operations.audit(user.username, "UPDATE_ALARM_RULE", rule_id)
    return item

@app.get("/api/copilot/{machine_id}")
def maintenance_copilot(machine_id: str, user: UserInfo = Depends(current_user)):
    item = copilot(machine_id)
    if not item: raise HTTPException(404, "Asset not found")
    return item

@app.get("/api/analytics")
def analytics():
    return build_analytics()

@app.get("/api/analytics/trends")
def analytics_trends(user: UserInfo = Depends(current_user)):
    return kpi_trends()

@app.get("/api/export/telemetry.csv")
def export_telemetry(user: UserInfo = Depends(current_user)):
    return telemetry_csv()

@app.get("/api/settings")
def get_platform_settings(user: UserInfo = Depends(current_user)):
    return platform_settings()

@app.patch("/api/settings")
def update_platform_settings(body: PlatformSettingsPatch, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    item=patch_platform_settings(body); operations.audit(user.username, "UPDATE_SETTINGS", "platform"); return item

@app.get("/api/admin/backup")
def backup(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    return backup_snapshot()

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return metrics_text()

@app.get("/api/hierarchy")
def plant_hierarchy(user: UserInfo = Depends(current_user)):
    return hierarchy()

@app.get("/api/reliability")
def reliability(user: UserInfo = Depends(current_user)):
    return reliability_kpis()

@app.get("/api/incidents")
def incident_list(user: UserInfo = Depends(current_user)):
    return incidents.list()

@app.post("/api/incidents", status_code=201)
def incident_create(body: IncidentCreate, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403, "Read-only role")
    if not store.machine(body.asset_id): raise HTTPException(404, "Asset not found")
    item=incidents.create(body,user.username); operations.audit(user.username,"CREATE_INCIDENT",item["id"]); return item

@app.post("/api/incidents/{incident_id}/resolve")
def incident_resolve(incident_id: str, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403, "Read-only role")
    item=incidents.resolve(incident_id)
    if not item: raise HTTPException(404,"Incident not found")
    operations.audit(user.username,"RESOLVE_INCIDENT",incident_id); return item

@app.get("/api/api-keys")
def api_key_list(user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403,"Admin role required")
    return api_keys.list()

@app.post("/api/api-keys", status_code=201)
def api_key_create(body: ApiKeyCreate, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403,"Admin role required")
    item=api_keys.create(body.name, body.scopes); operations.audit(user.username,"CREATE_API_KEY",item["id"]); return item


@app.get("/api/events")
def recent_events(limit: int = Query(100, ge=1, le=500), user: UserInfo = Depends(current_user)):
    return event_bus.recent(limit)

@app.get("/api/rule-engine")
def runtime_rules(user: UserInfo = Depends(current_user)):
    return rule_engine.list()

@app.get("/api/anomalies")
def anomaly_history(user: UserInfo = Depends(current_user)):
    return anomaly_pipeline.fleet()

@app.get("/api/anomalies/{machine_id}")
def anomaly_asset(machine_id: str, user: UserInfo = Depends(current_user)):
    item=anomaly_pipeline.score_asset(machine_id)
    if not item: raise HTTPException(404,"No telemetry available")
    return item

@app.post("/api/rule-engine", status_code=201)
def create_runtime_rule(body: RuleCreate, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    item=rule_engine.create(body); operations.audit(user.username,"CREATE_RUNTIME_RULE",item["id"]); return item

@app.delete("/api/rule-engine/{rule_id}", status_code=204)
def delete_runtime_rule(rule_id: str, user: UserInfo = Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin role required")
    if not rule_engine.delete(rule_id): raise HTTPException(404,"Rule not found")
    operations.audit(user.username,"DELETE_RUNTIME_RULE",rule_id)

@app.get("/api/correlations")
def correlations(user: UserInfo = Depends(current_user)): return autonomous.correlations()

@app.get("/api/root-cause/{machine_id}")
def root_cause(machine_id: str, user: UserInfo = Depends(current_user)):
    if not store.machine(machine_id): raise HTTPException(404,"Machine not found")
    return autonomous.root_cause(machine_id)

@app.get("/api/model-registry")
def model_registry(user: UserInfo = Depends(current_user)): return autonomous.model_registry()


@app.get("/api/manufacturing/dashboard")
def manufacturing_dashboard(user: UserInfo = Depends(current_user)): return manufacturing.dashboard()

@app.get("/api/manufacturing/shifts")
def manufacturing_shifts(user: UserInfo = Depends(current_user)): return manufacturing.shifts()

@app.get("/api/manufacturing/downtime")
def manufacturing_downtime(user: UserInfo = Depends(current_user)): return manufacturing.downtime

@app.post("/api/manufacturing/downtime", status_code=201)
def create_downtime(body: DowntimeCreate, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    if not store.machine(body.asset_id): raise HTTPException(404,"Asset not found")
    item=manufacturing.record_downtime(body,user.username); operations.audit(user.username,"RECORD_DOWNTIME",item["id"]); return item

@app.get("/api/spare-parts")
def spare_parts(user: UserInfo = Depends(current_user)): return list(manufacturing.parts.values())

@app.post("/api/spare-parts", status_code=201)
def create_spare_part(body: SparePartCreate, user: UserInfo = Depends(current_user)):
    if user.role not in ("ADMIN","OPERATOR"): raise HTTPException(403,"Write access required")
    return manufacturing.add_part(body)

@app.get("/api/escalation-policies")
def escalation_policies(user: UserInfo = Depends(current_user)): return manufacturing.escalations

@app.post("/api/incidents/{incident_id}/rca-review")
def rca_review(incident_id: str, body: RcaReview, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    return manufacturing.review_rca(incident_id,body,user.username)

@app.get("/api/mes/dashboard")
def mes_dashboard(user: UserInfo = Depends(current_user)): return mes.executive()

@app.get("/api/mes/products")
def mes_products(user: UserInfo = Depends(current_user)): return list(mes.products.values())

@app.get("/api/mes/orders")
def mes_orders(user: UserInfo = Depends(current_user)): return mes.orders

@app.post("/api/mes/orders", status_code=201)
def mes_create_order(body: ProductionOrderCreate, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    try: item=mes.create_order(body,user.username)
    except KeyError: raise HTTPException(404,"Product SKU not found")
    operations.audit(user.username,"CREATE_PRODUCTION_ORDER",item["id"]); return item

@app.patch("/api/mes/orders/{order_id}")
def mes_report_order(order_id: str, body: ProductionReport, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    item=mes.report(order_id,body)
    if not item: raise HTTPException(404,"Production order not found")
    return item

@app.get("/api/mes/andon")
def mes_andon(user: UserInfo = Depends(current_user)): return mes.andon()

@app.patch("/api/mes/machine-state/{asset_id}")
def mes_machine_state(asset_id: str, body: MachineStatePatch, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    if not store.machine(asset_id): raise HTTPException(404,"Asset not found")
    return mes.set_state(asset_id,body,user.username)

@app.get("/api/mes/quality")
def mes_quality(user: UserInfo = Depends(current_user)): return mes.inspections

@app.post("/api/mes/quality", status_code=201)
def mes_quality_create(body: QualityInspectionCreate, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    if not any(x["id"]==body.order_id for x in mes.orders): raise HTTPException(404,"Production order not found")
    return mes.inspect(body,user.username)

@app.get("/api/mes/handovers")
def mes_handovers(user: UserInfo = Depends(current_user)): return mes.handovers

@app.post("/api/mes/handovers", status_code=201)
def mes_handover_create(body: HandoverCreate, user: UserInfo = Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    return mes.handover(body,user.username)

@app.get("/api/mes/genealogy")
def mes_genealogy(user: UserInfo = Depends(current_user)): return mes.genealogy()

@app.get("/api/overview")
def overview():
    latest_items = store.latest()
    machines_items = store.machines()
    alerts_items = store.alerts()
    work = operations.work_orders()
    enabled = [m for m in machines_items if m.enabled]
    reporting_ids = {item.machine_id for item in latest_items}
    availability = round((sum(m.id in reporting_ids for m in enabled) / len(enabled) * 100) if enabled else 100, 1)
    avg_anomaly = sum(item.anomaly_score for item in latest_items) / max(1, len(latest_items))
    performance = round(max(0, 100 - avg_anomaly * 35), 1)
    quality = round(max(0, 100 - sum(item.status.value == "CRITICAL" for item in latest_items) * 4), 1)
    oee = round(availability * performance * quality / 10000, 1)
    return {
        "machines": len(machines_items), "online": len(reporting_ids),
        "critical": sum(x.status.value == "CRITICAL" for x in latest_items),
        "warnings": sum(x.status.value == "WARNING" for x in latest_items),
        "unacknowledged_alerts": sum(not x.acknowledged for x in alerts_items),
        "open_work_orders": sum(x.status == "OPEN" for x in work),
        "oee": oee, "availability": availability, "performance": performance, "quality": quality,
    }

@app.websocket("/ws/live")
async def live(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4401); return
    try:
        user_from_access_token(token)
    except HTTPException:
        await ws.close(code=4401); return
    await ws.accept()
    try:
        while True:
            await ws.send_json({
                "telemetry": [x.model_dump(mode="json") for x in store.latest()],
                "overview": overview(),
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass

@app.get("/api/advanced-mes/schedule")
def am_schedule(user:UserInfo=Depends(current_user)):return advanced_mes.schedule()
@app.get("/api/advanced-mes/work-centers")
def am_wc(user:UserInfo=Depends(current_user)):return advanced_mes.work_centers
@app.get("/api/advanced-mes/bom")
def am_bom(user:UserInfo=Depends(current_user)):return advanced_mes.bom
@app.get("/api/advanced-mes/routing")
def am_route(user:UserInfo=Depends(current_user)):return advanced_mes.routing
@app.get("/api/advanced-mes/wip")
def am_wip(user:UserInfo=Depends(current_user)):return advanced_mes.wip()
@app.get("/api/advanced-mes/spc")
def am_spc(user:UserInfo=Depends(current_user)):return advanced_mes.spc()
@app.get("/api/advanced-mes/ncr")
def am_ncr(user:UserInfo=Depends(current_user)):return advanced_mes.ncr
@app.post("/api/advanced-mes/ncr",status_code=201)
def am_ncr_new(body:NCRCreate,user:UserInfo=Depends(current_user)):
 if user.role=="VIEWER":raise HTTPException(403,"Read-only role")
 return advanced_mes.create_ncr(body,user.username)
@app.patch("/api/advanced-mes/ncr/{nid}/capa")
def am_capa(nid:str,body:CAPAPatch,user:UserInfo=Depends(current_user)):
 if user.role=="VIEWER":raise HTTPException(403,"Read-only role")
 x=advanced_mes.capa(nid,body)
 if not x:raise HTTPException(404,"NCR not found")
 return x
@app.get("/api/advanced-mes/instructions")
def am_wi(user:UserInfo=Depends(current_user)):return advanced_mes.instructions
@app.get("/api/advanced-mes/costs")
def am_cost(user:UserInfo=Depends(current_user)):return advanced_mes.costs()


# Stage 15 — Smart Factory Digital Twin & Optimization
@app.get("/api/factory-twin/snapshot")
def twin_snapshot(user:UserInfo=Depends(current_user)): return factory_twin.snapshot()
@app.get("/api/factory-twin/capacity")
def twin_capacity(user:UserInfo=Depends(current_user)): return factory_twin.capacity()
@app.post("/api/factory-twin/scenarios")
def twin_scenario(body:ScenarioRequest,user:UserInfo=Depends(current_user)): return factory_twin.scenario(body)
@app.get("/api/factory-twin/conflicts")
def twin_conflicts(user:UserInfo=Depends(current_user)): return factory_twin.conflicts()
@app.get("/api/factory-twin/predictive-quality")
def twin_quality(user:UserInfo=Depends(current_user)): return factory_twin.predictive_quality()


# Stage 16: AI Factory Copilot & Decision Intelligence
@app.post("/api/copilot/ask")
def copilot_ask(body:CopilotQuery,user:UserInfo=Depends(current_user)):
    return factory_copilot.ask(body)

@app.get("/api/copilot/recommendations")
def copilot_recommendations(user:UserInfo=Depends(current_user)):
    return factory_copilot.recommendations()

@app.get("/api/copilot/shift-briefing")
def copilot_shift_briefing(user:UserInfo=Depends(current_user)):
    return factory_copilot.shift_briefing()

@app.get("/api/copilot/executive-briefing")
def copilot_executive_briefing(user:UserInfo=Depends(current_user)):
    return factory_copilot.executive_briefing()

@app.get("/api/copilot/approvals")
def copilot_approvals(user:UserInfo=Depends(current_user)):
    return factory_copilot.approvals()

@app.post("/api/copilot/approvals")
def copilot_approval(body:ApprovalRequest,user:UserInfo=Depends(current_user)):
    if user.role == "VIEWER": raise HTTPException(403,"Read-only role")
    item=factory_copilot.approval(body,user.username)
    if not item: raise HTTPException(404,"Recommendation not found")
    operations.audit(user.username,"COPILOT_RECOMMENDATION_"+body.decision,body.recommendation_id)
    return item


# Stage 17 — Enterprise AI/RAG & Knowledge Platform
@app.get("/api/knowledge/documents")
def knowledge_documents(user:UserInfo=Depends(current_user)): return knowledge_rag.docs

@app.post("/api/knowledge/documents",status_code=201)
def knowledge_add(body:KnowledgeDocumentCreate,user:UserInfo=Depends(current_user)):
    if user.role=="VIEWER": raise HTTPException(403,"Read-only role")
    item=knowledge_rag.add(body,user.username); operations.audit(user.username,"ADD_KNOWLEDGE",item["id"]); return item

@app.get("/api/knowledge/search")
def knowledge_search(q:str=Query(min_length=2,max_length=300),asset_id:str|None=None,user:UserInfo=Depends(current_user)): return knowledge_rag.search(q,asset_id)

@app.post("/api/rag/ask")
def rag_ask(body:RagQuery,user:UserInfo=Depends(current_user)):
    guard=knowledge_rag.guard(body.question)
    if not guard["allowed"]:
        response={"answer":guard["message"],"confidence":1.0,"citations":[],"guardrail":guard,"blocked":True,"actions":[]}
        response["conversation_id"]=knowledge_rag.record(body.conversation_id,user.username,body.question,response); return response
    base=factory_copilot.ask(CopilotQuery(question=body.question,asset_id=body.asset_id))
    docs=knowledge_rag.search(body.question,body.asset_id,4)
    citations=[{"id":d["id"],"title":d["title"],"kind":d["kind"],"version":d["version"],"score":d["score"],"excerpt":d["excerpt"]} for d in docs]
    answer=base["answer"]
    if docs: answer += " Knowledge evidence: " + " ".join(d["excerpt"] for d in docs[:2])
    response={**base,"answer":answer,"citations":citations,"guardrail":guard,"blocked":False,"provider":"LOCAL_GROUNDED_RAG"}
    response["confidence"]=round(min(.96,base["confidence"]+(0.08 if docs else -0.08)),2)
    response["conversation_id"]=knowledge_rag.record(body.conversation_id,user.username,body.question,response); return response

@app.get("/api/rag/conversations/{conversation_id}")
def rag_history(conversation_id:str,user:UserInfo=Depends(current_user)): return knowledge_rag.history.get(conversation_id,[])

@app.get("/api/ai-governance")
def ai_governance(user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    return knowledge_rag.governance()


# Stage 18: Enterprise Security & Zero-Trust
def _admin(user):
    if user.role != "ADMIN": raise HTTPException(403,"Admin role required")

@app.get("/api/security/posture")
def security_posture(user: UserInfo = Depends(current_user)):
    _admin(user); return {**security.posture(),"permission_catalog":PERMISSION_CATALOG}

@app.get("/api/security/events")
def security_events(user: UserInfo = Depends(current_user)):
    _admin(user); return security.events

@app.post("/api/security/mfa/enroll")
def mfa_enroll(user: UserInfo = Depends(current_user)):
    secret=generate_totp_secret(); raw,hashed=recovery_codes(); security.mfa[user.username]={"secret":secret,"enabled":False,"recovery_hashes":hashed}; security.event("MFA_ENROLL_STARTED",user.username,"INFO"); return {"secret":secret,"otpauth_uri":f"otpauth://totp/AshkanIIoT:{user.username}?secret={secret}&issuer=AshkanIIoT","recovery_codes":raw,"note":"Secret and recovery codes are shown once; store them securely."}

@app.post("/api/security/mfa/verify")
def mfa_verify(body:MfaVerify,user: UserInfo = Depends(current_user)):
    item=security.mfa.get(user.username);
    if not item or not verify_totp(item["secret"],body.code): raise HTTPException(400,"Invalid TOTP code")
    item["enabled"]=True; security.event("MFA_ENABLED",user.username,"INFO"); return {"enabled":True}

@app.get("/api/security/sessions")
def session_inventory(user: UserInfo = Depends(current_user)):
    return [{"id":"current","user":user.username,"device":"Current browser","trust":"VERIFIED","last_seen":"now","revocable":False}]

@app.get("/api/security/password-policy")
def password_policy_info(user: UserInfo = Depends(current_user)):
    return {"min_length":12,"requirements":["uppercase","lowercase","number","symbol"],"lockout":"5 failures / 15 minutes","refresh_rotation":True}


# Stage 19 — Enterprise Integration & Event-Driven Platform
@app.get("/api/integrations/status")
def integration_status(user:UserInfo=Depends(current_user)): return integration_hub.status()
@app.get("/api/integrations/connectors")
def integration_connectors(user:UserInfo=Depends(current_user)): return integration_hub.connectors()
@app.patch("/api/integrations/connectors/{connector_id}")
def integration_connector_patch(connector_id:str,body:ConnectorPatch,user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    item=integration_hub.patch_connector(connector_id,body.enabled if body.enabled is not None else False)
    if not item: raise HTTPException(404,"Connector not found")
    operations.audit(user.username,"UPDATE_CONNECTOR",connector_id); return item
@app.get("/api/integrations/outbox")
def integration_outbox(user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    return integration_hub.outbox()
@app.post("/api/integrations/dispatch")
def integration_dispatch(user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    return integration_hub.dispatch_once()
@app.get("/api/integrations/dlq")
def integration_dlq(user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    return integration_hub.dlq()
@app.post("/api/integrations/dlq/{event_id}/retry")
def integration_retry(event_id:str,user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    item=integration_hub.retry_dlq(event_id)
    if not item: raise HTTPException(404,"DLQ event not found")
    return item
@app.get("/api/integrations/webhooks")
def integration_webhooks(user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    return integration_hub.webhooks()
@app.post("/api/integrations/webhooks",status_code=201)
def integration_webhook_create(body:WebhookCreate,user:UserInfo=Depends(current_user)):
    if user.role!="ADMIN": raise HTTPException(403,"Admin role required")
    item=integration_hub.add_webhook(body); operations.audit(user.username,"CREATE_WEBHOOK",item["id"]); return item
