def login(client, username='admin', password='Admin123!'):
    r=client.post('/api/auth/login',json={'username':username,'password':password}); assert r.status_code==200
    return {'Authorization':f"Bearer {r.json()['access_token']}"}

def test_copilot_grounded_briefings(client):
    h=login(client)
    for path in ('/api/copilot/recommendations','/api/copilot/shift-briefing','/api/copilot/executive-briefing'):
        r=client.get(path,headers=h); assert r.status_code==200

def test_copilot_answer_has_guardrail_and_sources(client):
    h=login(client)
    r=client.post('/api/copilot/ask',headers=h,json={'question':'Explain current OEE and the main bottleneck'})
    assert r.status_code==200
    data=r.json(); assert data['guardrail']; assert data['sources']; assert 0 <= data['confidence'] <= 1

def test_viewer_cannot_approve_recommendation(client):
    admin=login(client); recs=client.get('/api/copilot/recommendations',headers=admin).json()
    if not recs: return
    viewer=login(client,'viewer','Viewer123!')
    r=client.post('/api/copilot/approvals',headers=viewer,json={'recommendation_id':recs[0]['id'],'decision':'APPROVED','note':'test'})
    assert r.status_code==403
