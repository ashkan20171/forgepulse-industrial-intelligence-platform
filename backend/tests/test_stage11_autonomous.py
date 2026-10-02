from app.autonomous import autonomous, RuleCreate
from app.rule_engine import rule_engine

def test_model_registry_has_production_model():
    models=autonomous.model_registry(); assert any(x['stage']=='PRODUCTION' for x in models)

def test_runtime_rule_builder_create_delete():
    r=rule_engine.create(RuleCreate(name='Test pressure rule',metric='pressure',operator='>=',threshold=8,severity='HIGH'))
    assert any(x['id']==r['id'] for x in rule_engine.list())
    assert rule_engine.delete(r['id']) is True
