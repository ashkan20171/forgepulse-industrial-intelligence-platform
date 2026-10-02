from app.integration_hub import integration_hub

def test_connector_catalog_has_enterprise_boundaries():
    kinds={x['kind'] for x in integration_hub.connectors()}
    assert {'ERP','MES','CMMS','OT'} <= kinds

def test_integration_semantics_are_explicit():
    s=integration_hub.status()
    assert s['delivery_semantics']=='at-least-once'
    assert 'Idempotency-Key' in s['idempotency']
