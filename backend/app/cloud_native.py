from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import time
from dataclasses import dataclass, asdict
from threading import Lock
from typing import Callable, TypeVar

from .persistence import ping as postgres_ping
from .distributed import redis_ping

log = logging.getLogger(__name__)
T = TypeVar("T")

@dataclass
class RuntimeState:
    started_at: float = time.time()
    accepting_traffic: bool = True
    shutting_down: bool = False
    inflight_requests: int = 0

    def snapshot(self) -> dict:
        data = asdict(self)
        data["uptime_seconds"] = round(time.time() - self.started_at, 2)
        data["pod"] = os.getenv("HOSTNAME", socket.gethostname())
        return data

runtime = RuntimeState()
_runtime_lock = Lock()

class CircuitOpen(RuntimeError):
    pass

class CircuitBreaker:
    """Small dependency-free circuit breaker suitable for adapter boundaries."""
    def __init__(self, name: str, failure_threshold: int = 5, recovery_seconds: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failures = 0
        self.opened_at: float | None = None
        self._lock = Lock()

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        with self._lock:
            if self.opened_at and time.time() - self.opened_at < self.recovery_seconds:
                raise CircuitOpen(f"Circuit {self.name} is open")
            if self.opened_at:
                self.opened_at = None
                self.failures = 0
        try:
            value = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self.failures += 1
                if self.failures >= self.failure_threshold:
                    self.opened_at = time.time()
            raise
        with self._lock:
            self.failures = 0
        return value

    def state(self) -> dict:
        return {"name": self.name, "state": "OPEN" if self.opened_at else "CLOSED", "failures": self.failures}

class Bulkhead:
    """Async concurrency bulkhead for expensive external adapters."""
    def __init__(self, max_concurrency: int = 20):
        self._sem = asyncio.Semaphore(max_concurrency)

    async def run(self, coro):
        async with self._sem:
            return await coro

postgres_circuit = CircuitBreaker("postgres")
redis_circuit = CircuitBreaker("redis")
external_bulkhead = Bulkhead(20)


def liveness() -> dict:
    return {"status": "alive", **runtime.snapshot()}


def readiness() -> tuple[bool, dict]:
    if not runtime.accepting_traffic or runtime.shutting_down:
        return False, {"status": "draining", **runtime.snapshot()}
    dependencies = {}
    for name, check, circuit in (
        ("postgres", postgres_ping, postgres_circuit),
        ("redis", redis_ping, redis_circuit),
    ):
        try:
            dependencies[name] = bool(circuit.call(check))
        except Exception as exc:
            log.warning("readiness dependency %s failed: %s", name, exc)
            dependencies[name] = False
    ready = all(dependencies.values())
    return ready, {"status": "ready" if ready else "not-ready", "dependencies": dependencies, **runtime.snapshot()}


def startup() -> tuple[bool, dict]:
    # Startup intentionally checks only process initialization. Dependency readiness is separate,
    # preventing Kubernetes from endlessly restarting a healthy process during a DB outage.
    ok = (time.time() - runtime.started_at) >= 0
    return ok, {"status": "started" if ok else "starting", **runtime.snapshot()}


def begin_drain() -> None:
    with _runtime_lock:
        runtime.accepting_traffic = False
        runtime.shutting_down = True
    log.info("Instance entered graceful drain mode")


def request_started() -> None:
    with _runtime_lock:
        runtime.inflight_requests += 1


def request_finished() -> None:
    with _runtime_lock:
        runtime.inflight_requests = max(0, runtime.inflight_requests - 1)
