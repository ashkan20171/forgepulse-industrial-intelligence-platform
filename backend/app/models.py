from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class Severity(str, Enum):
    normal = "NORMAL"
    warning = "WARNING"
    critical = "CRITICAL"

class TelemetryIn(BaseModel):
    machine_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    temperature: float = Field(ge=-100, le=500)
    vibration: float = Field(ge=0, le=100)
    pressure: float | None = Field(default=None, ge=0, le=1000)
    rpm: float | None = Field(default=None, ge=0, le=100000)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

class TelemetryOut(TelemetryIn):
    status: Severity
    anomaly_score: float = Field(ge=0, le=1)

class Machine(BaseModel):
    id: str
    name: str
    location: str
    type: str
    enabled: bool = True
    temperature_warning: float = 75
    temperature_critical: float = 85
    vibration_warning: float = 5
    vibration_critical: float = 7

class MachinePatch(BaseModel):
    enabled: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=120)

class Alert(BaseModel):
    id: str
    machine_id: str
    severity: Severity
    title: str
    message: str
    timestamp: datetime
    acknowledged: bool = False
