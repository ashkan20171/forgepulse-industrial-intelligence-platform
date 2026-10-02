from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from .models import Alert, Machine, Severity, TelemetryIn, TelemetryOut

class TelemetryStore:
    def __init__(self, history_size: int = 500):
        self._lock = RLock()
        self._history = defaultdict(lambda: deque(maxlen=history_size))
        self._machines: dict[str, Machine] = {
            "motor_01": Machine(id="motor_01", name="Main Drive Motor", location="Line A", type="Motor"),
            "pump_01": Machine(id="pump_01", name="Cooling Pump", location="Utility", type="Pump"),
            "fan_01": Machine(id="fan_01", name="Exhaust Fan", location="Line B", type="Fan"),
        }
        self._alerts: deque[Alert] = deque(maxlen=250)

    def machines(self):
        with self._lock: return list(self._machines.values())

    def machine(self, machine_id: str):
        with self._lock: return self._machines.get(machine_id)

    def update_machine(self, machine_id: str, **changes):
        with self._lock:
            machine = self._machines.get(machine_id)
            if not machine: return None
            updated = machine.model_copy(update={k:v for k,v in changes.items() if v is not None})
            self._machines[machine_id] = updated
            return updated

    def ingest(self, data: TelemetryIn) -> TelemetryOut | None:
        with self._lock:
            machine = self._machines.get(data.machine_id)
            if not machine:
                machine = Machine(id=data.machine_id, name=data.machine_id.replace('_',' ').title(), location="Unassigned", type="Unknown")
                self._machines[data.machine_id] = machine
            if not machine.enabled: return None
            t_ratio = max(0.0, (data.temperature - machine.temperature_warning) / max(1, machine.temperature_critical-machine.temperature_warning))
            v_ratio = max(0.0, (data.vibration - machine.vibration_warning) / max(0.1, machine.vibration_critical-machine.vibration_warning))
            score = min(1.0, max(t_ratio, v_ratio))
            status = Severity.critical if data.temperature >= machine.temperature_critical or data.vibration >= machine.vibration_critical else Severity.warning if data.temperature >= machine.temperature_warning or data.vibration >= machine.vibration_warning else Severity.normal
            out = TelemetryOut(**data.model_dump(), status=status, anomaly_score=round(score, 3))
            previous = self._history[data.machine_id][-1].status if self._history[data.machine_id] else Severity.normal
            self._history[data.machine_id].append(out)
            if status != Severity.normal and status != previous:
                self._alerts.appendleft(Alert(id=str(uuid4()), machine_id=data.machine_id, severity=status, title=f"{status.value.title()} condition detected", message=f"Temperature {data.temperature:.1f}°C · Vibration {data.vibration:.2f} mm/s", timestamp=datetime.now(timezone.utc)))
            return out

    def latest(self):
        with self._lock: return [items[-1] for items in self._history.values() if items]

    def history(self, machine_id: str, limit=100):
        with self._lock: return list(self._history[machine_id])[-limit:]

    def alerts(self):
        with self._lock: return list(self._alerts)

    def acknowledge(self, alert_id: str):
        with self._lock:
            for idx, alert in enumerate(self._alerts):
                if alert.id == alert_id:
                    self._alerts[idx] = alert.model_copy(update={"acknowledged": True})
                    return self._alerts[idx]
            return None

store = TelemetryStore()
