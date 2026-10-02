import json, logging, re
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from .config import settings
from .database import db_manager
from .models import TelemetryIn
from .store import store
logger = logging.getLogger(__name__)
TOPIC_REGEX = re.compile(r"^factory/sensor/([^/]+)/metrics$")

class MQTTService:
    def __init__(self):
        self.connected = False
        self.client = mqtt.Client(client_id="industrial-iot-ingestion", clean_session=True)
        self.client.on_connect = self._on_connect; self.client.on_disconnect = self._on_disconnect; self.client.on_message = self._on_message
    def _on_connect(self, client, userdata, flags, rc):
        self.connected = rc == 0
        if self.connected: client.subscribe(settings.MQTT_TOPIC); logger.info("MQTT connected")
        else: logger.warning("MQTT connection failed: %s", rc)
    def _on_disconnect(self, client, userdata, rc): self.connected = False
    def _on_message(self, client, userdata, msg):
        try:
            match = TOPIC_REGEX.match(msg.topic)
            if not match: return
            payload = json.loads(msg.payload.decode("utf-8"))
            timestamp = payload.get("timestamp")
            if isinstance(timestamp, (int,float)): timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            metric = TelemetryIn(machine_id=match.group(1), temperature=payload["temperature"], vibration=payload["vibration"], pressure=payload.get("pressure"), rpm=payload.get("rpm"), **({"timestamp": timestamp} if timestamp else {}))
            saved = store.ingest(metric)
            if saved: db_manager.write(saved)
        except Exception: logger.exception("Invalid MQTT message on %s", msg.topic)
    def start(self):
        if not settings.MQTT_ENABLED: return
        try:
            self.client.connect_async(settings.MQTT_BROKER, settings.MQTT_PORT, 60); self.client.loop_start()
        except Exception: logger.exception("Unable to start MQTT")
    def stop(self):
        try: self.client.loop_stop(); self.client.disconnect()
        except Exception: pass
mqtt_service = MQTTService()
