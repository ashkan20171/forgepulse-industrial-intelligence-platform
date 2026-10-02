from app.cloud_native import CircuitBreaker, runtime, liveness, startup

def test_liveness_is_process_scoped():
    assert liveness()["status"] == "alive"

def test_startup_is_independent_of_downstream_dependencies():
    ok, payload = startup()
    assert ok is True
    assert payload["status"] == "started"

def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker("test", failure_threshold=2, recovery_seconds=60)
    def fail(): raise RuntimeError("boom")
    for _ in range(2):
        try: cb.call(fail)
        except RuntimeError: pass
    assert cb.state()["state"] == "OPEN"
