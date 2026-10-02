from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from .store import store
from .operations import operations


def build_analytics() -> dict:
    latest = store.latest()
    alerts = store.alerts()
    work_orders = operations.work_orders()
    status_counts = Counter(item.status.value for item in latest)
    risk = sorted(
        ({"machine_id": item.machine_id, "score": round(item.anomaly_score * 100, 1), "status": item.status.value}
         for item in latest),
        key=lambda item: item["score"], reverse=True,
    )
    return {
        "generated_at": datetime.now(timezone.utc),
        "fleet_status": {key: status_counts.get(key, 0) for key in ("NORMAL", "WARNING", "CRITICAL")},
        "top_risks": risk[:5],
        "alerts": {"total": len(alerts), "open": sum(not a.acknowledged for a in alerts)},
        "maintenance": {
            "open": sum(w.status == "OPEN" for w in work_orders),
            "completed": sum(w.status == "COMPLETED" for w in work_orders),
            "critical_priority": sum(w.status == "OPEN" and w.priority == "CRITICAL" for w in work_orders),
        },
    }
