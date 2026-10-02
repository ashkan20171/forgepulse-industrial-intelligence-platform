def auth(client):
    r=client.post('/api/auth/login',json={'username':'admin','password':'Admin@123'}); assert r.status_code==200; return {'Authorization':'Bearer '+r.json()['access_token']}
def test_manufacturing_dashboard(client):
    r=client.get('/api/manufacturing/dashboard',headers=auth(client)); assert r.status_code==200; assert 'oee' in r.json() and 'downtime_losses' in r.json()
def test_spare_parts(client):
    r=client.get('/api/spare-parts',headers=auth(client)); assert r.status_code==200; assert len(r.json())>=1
