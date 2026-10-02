def test_stage14_requires_auth(client):
    assert client.get('/api/advanced-mes/schedule').status_code == 401

def test_stage14_planning(admin_client):
    assert admin_client.get('/api/advanced-mes/bom').status_code == 200
    assert admin_client.get('/api/advanced-mes/routing').status_code == 200
    assert admin_client.get('/api/advanced-mes/spc').json()['process_status'] == 'IN_CONTROL'
