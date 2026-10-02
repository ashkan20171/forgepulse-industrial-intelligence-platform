from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Ashkan Industrial IoT Platform"
    APP_VERSION: str = "21.0.0"
    ENVIRONMENT: str = "development"
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "factory/sensor/+/metrics"
    MQTT_ENABLED: bool = True
    INFLUXDB_URL: str = "http://localhost:8086"
    INFLUXDB_TOKEN: str = "change-me"
    INFLUXDB_ORG: str = "industrial_io"
    INFLUXDB_BUCKET: str = "sensor_data"
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000,null"
    AUTH_SECRET: str = "change-this-in-production"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 7
    RATE_LIMIT_PER_MINUTE: int = 120
    POSTGRES_URL: str = "sqlite:///./forgepulse-local.db"
    REDIS_URL: str = "redis://redis:6379/0"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"
    SHUTDOWN_GRACE_SECONDS: int = 20
    INSTANCE_ID: str = ""
    DEMO_ADMIN_PASSWORD: str = "Admin@123"
    DEMO_OPERATOR_PASSWORD: str = "Operator@123"
    DEMO_VIEWER_PASSWORD: str = "Viewer@123"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
