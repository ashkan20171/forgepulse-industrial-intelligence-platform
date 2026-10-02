def login(client):
    r=client.post('/api/auth/login',json={'username':'admin','password':'admin123'})
    assert r.status_code==200
    return {'Authorization':f"Bearer {r.json()['access_token']}"}

def test_factory_twin_snapshot_and_capacity(client):
    h=login(client)
    snap=client.get('/api/factory-twin/snapshot',headers=h); assert snap.status_code==200
    assert 0 <= snap.json()['oee'] <= 100
    cap=client.get('/api/factory-twin/capacity',headers=h); assert cap.status_code==200
    assert cap.json()['bottleneck']

def test_what_if_scenario_is_explainable(client):
    h=login(client)
    r=client.post('/api/factory-twin/scenarios',headers=h,json={'demand_multiplier':1.15,'speed_improvement_pct':5,'downtime_reduction_pct':10,'quality_improvement_pct':1})
    assert r.status_code==200
    body=r.json(); assert body['explanation'] and body['constraint_risk'] in ('LOW','MEDIUM','HIGH')
