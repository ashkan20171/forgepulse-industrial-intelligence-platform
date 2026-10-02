def token(client, username='admin', password='Admin@123'):
    r=client.post('/api/auth/login',json={'username':username,'password':password}); return r.json()['access_token']
def auth(t): return {'Authorization':f'Bearer {t}'}
def test_mes_dashboard_and_orders(client):
    t=token(client); assert client.get('/api/mes/dashboard',headers=auth(t)).status_code==200
    r=client.get('/api/mes/orders',headers=auth(t)); assert r.status_code==200 and len(r.json())>=2
def test_viewer_cannot_create_order(client):
    t=token(client,'viewer','Viewer@123'); payload={'product_sku':'SKU-PUMP-01','line':'Assembly Line 1','target_qty':10,'planned_cycle_seconds':72,'shift_id':'SHIFT-A'}
    assert client.post('/api/mes/orders',headers=auth(t),json=payload).status_code==403
def test_andon_and_genealogy(client):
    t=token(client); assert client.get('/api/mes/andon',headers=auth(t)).status_code==200; assert client.get('/api/mes/genealogy',headers=auth(t)).status_code==200
