import logging
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from .config import settings
from .models import TelemetryOut

logger = logging.getLogger(__name__)

class InfluxDBManager:
    def __init__(self):
        self.client = None
        self.write_api = None
    def connect(self):
        if self.client: return
        self.client = InfluxDBClient(url=settings.INFLUXDB_URL, token=settings.INFLUXDB_TOKEN, org=settings.INFLUXDB_ORG, timeout=3000)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
    def ping(self) -> bool:
        try:
            self.connect(); return bool(self.client.ping())
        except Exception: return False
    def write(self, metric: TelemetryOut):
        try:
            self.connect()
            point = Point("machine_telemetry").tag("machine_id", metric.machine_id).tag("status", metric.status.value).field("temperature", metric.temperature).field("vibration", metric.vibration).field("anomaly_score", metric.anomaly_score).time(metric.timestamp)
            if metric.pressure is not None: point.field("pressure", metric.pressure)
            if metric.rpm is not None: point.field("rpm", metric.rpm)
            self.write_api.write(bucket=settings.INFLUXDB_BUCKET, org=settings.INFLUXDB_ORG, record=point)
        except Exception as exc:
            logger.warning("InfluxDB write skipped: %s", exc)
    def close(self):
        if self.client: self.client.close()

db_manager = InfluxDBManager()
