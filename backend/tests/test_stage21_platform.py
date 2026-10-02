def test_platform_overview_requires_admin(client, admin_headers):
    r=client.get('/api/platform-engineering/overview',headers=admin_headers); assert r.status_code==200
    assert r.json()['gitops']=='Argo CD'

def test_platform_flags(client, admin_headers):
    r=client.get('/api/platform-engineering/flags',headers=admin_headers); assert r.status_code==200
    assert any(x['key']=='dynamic_scheduling' for x in r.json())
