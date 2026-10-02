from app.rule_engine import rule_engine
from app.event_engine import event_bus
from app.models import TelemetryIn

def test_rule_engine_emits_event():
    before=len(event_bus.recent(500))
    fired=rule_engine.evaluate(TelemetryIn(machine_id='motor_01',temperature=90,vibration=8))
    assert fired and len(event_bus.recent(500)) > before
