import os
os.environ["MQTT_ENABLED"] = "false"

from fastapi.testclient import TestClient
from app.main import app


def login(client: TestClient, username="admin", password="Admin@123") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_login_and_ingestion():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        response = client.post("/api/telemetry", json={"machine_id": "motor_01", "temperature": 90, "vibration": 8})
        assert response.status_code == 201
        assert response.json()["status"] == "CRITICAL"
        assert client.get("/api/overview").json()["critical"] >= 1


def test_rbac_and_disable_machine_blocks_ingestion():
    with TestClient(app) as client:
        admin = login(client)
        viewer = login(client, "viewer", "Viewer@123")
        assert client.patch("/api/machines/pump_01", headers=viewer, json={"enabled": False}).status_code == 403
        assert client.patch("/api/machines/pump_01", headers=admin, json={"enabled": False}).status_code == 200
        assert client.post("/api/telemetry", json={"machine_id": "pump_01", "temperature": 60, "vibration": 2}).status_code == 409
        assert client.patch("/api/machines/pump_01", headers=admin, json={"enabled": True}).status_code == 200


def test_work_order_validation_and_admin_audit():
    with TestClient(app) as client:
        admin = login(client)
        viewer = login(client, "viewer", "Viewer@123")
        payload = {"asset_id": "motor_01", "title": "Inspect drive coupling", "priority": "HIGH", "assignee": "Maintenance"}
        assert client.post("/api/work-orders", headers=viewer, json=payload).status_code == 403
        assert client.post("/api/work-orders", headers=admin, json=payload).status_code == 201
        assert client.get("/api/audit", headers=viewer).status_code == 403
        assert client.get("/api/audit", headers=admin).status_code == 200
        assert client.get("/api/analytics").status_code == 200

def test_predictive_intelligence_devices_and_notifications():
    with TestClient(app) as client:
        admin = login(client)
        viewer = login(client, "viewer", "Viewer@123")
        client.post("/api/telemetry", json={"machine_id":"motor_01","temperature":91,"vibration":8.2})
        intel=client.get("/api/intelligence/motor_01")
        assert intel.status_code == 200
        assert 0 <= intel.json()["health_index"] <= 100
        assert intel.json()["drivers"]
        devices=client.get("/api/devices")
        assert devices.status_code == 200 and len(devices.json()) >= 3
        assert client.patch("/api/devices/motor_01", headers=viewer, json={"maintenance_mode":True}).status_code == 403
        assert client.patch("/api/devices/motor_01", headers=admin, json={"maintenance_mode":True}).status_code == 200
        notes=client.get("/api/notifications", headers=admin)
        assert notes.status_code == 200 and len(notes.json()) >= 1

def test_stage6_asset_detail_rules_calendar_and_copilot():
    with TestClient(app) as client:
        admin = login(client)
        viewer = login(client, "viewer", "Viewer@123")
        client.post("/api/telemetry", json={"machine_id":"motor_01","temperature":82,"vibration":6.2})
        detail = client.get("/api/assets/motor_01/detail")
        assert detail.status_code == 200
        assert detail.json()["asset"]["id"] == "motor_01"
        assert client.get("/api/copilot/motor_01", headers=viewer).status_code == 200
        rules = client.get("/api/alarm-rules", headers=viewer)
        assert rules.status_code == 200 and rules.json()
        rule_id = rules.json()[0]["id"]
        assert client.patch(f"/api/alarm-rules/{rule_id}", headers=viewer, json={"enabled":False}).status_code == 403
        assert client.patch(f"/api/alarm-rules/{rule_id}", headers=admin, json={"enabled":False}).status_code == 200
        assert client.get("/api/maintenance/calendar", headers=viewer).status_code == 200

def test_stage7_refresh_users_settings_export_and_metrics():
    with TestClient(app) as client:
        session = client.post('/api/auth/login', json={'username':'admin','password':'Admin@123'}).json()
        admin={'Authorization':f"Bearer {session['access_token']}"}
        viewer=login(client,'viewer','Viewer@123')
        refreshed=client.post('/api/auth/refresh',json={'refresh_token':session['refresh_token']})
        assert refreshed.status_code == 200 and refreshed.json()['access_token']
        assert client.post('/api/auth/refresh',json={'refresh_token':session['refresh_token']}).status_code == 401
        assert client.get('/api/users',headers=viewer).status_code == 403
        created=client.post('/api/users',headers=admin,json={'username':'maint1','display_name':'Maintenance Engineer','password':'Maintenance@123','role':'OPERATOR'})
        assert created.status_code == 201
        assert client.patch('/api/users/maint1',headers=admin,json={'role':'VIEWER'}).status_code == 200
        assert client.get('/api/analytics/trends',headers=viewer).status_code == 200
        csv=client.get('/api/export/telemetry.csv',headers=viewer)
        assert csv.status_code == 200 and 'text/csv' in csv.headers['content-type']
        assert client.patch('/api/settings',headers=viewer,json={'retention_days':90}).status_code == 403
        assert client.patch('/api/settings',headers=admin,json={'retention_days':90}).status_code == 200
        assert client.get('/api/admin/backup',headers=admin).status_code == 200
        metrics=client.get('/metrics'); assert metrics.status_code == 200 and 'ashkan_iot_assets' in metrics.text

def test_stage8_reliability_and_hierarchy(client, admin_headers):
    r=client.get('/api/reliability',headers=admin_headers); assert r.status_code==200; assert 'mtbf_hours' in r.json()
    h=client.get('/api/hierarchy',headers=admin_headers); assert h.status_code==200; assert h.json()[0]['lines']

def test_stage8_incident_lifecycle(client, operator_headers):
    created=client.post('/api/incidents',headers=operator_headers,json={'asset_id':'motor_01','title':'Bearing inspection required','severity':'HIGH'}); assert created.status_code==201
    resolved=client.post(f"/api/incidents/{created.json()['id']}/resolve",headers=operator_headers); assert resolved.status_code==200; assert resolved.json()['status']=='RESOLVED'
