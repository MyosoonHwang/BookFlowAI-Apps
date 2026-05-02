"""env-driven config (DASHBOARD_ prefix). No RDS direct - fan-in via HTTP."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DASHBOARD_", case_sensitive=False)

    inventory_svc_url:    str = "http://inventory-svc.bookflow.svc.cluster.local"
    forecast_svc_url:     str = "http://forecast-svc.bookflow.svc.cluster.local"
    decision_svc_url:     str = "http://decision-svc.bookflow.svc.cluster.local"
    notification_svc_url: str = "http://notification-svc.bookflow.svc.cluster.local"
    intervention_svc_url: str = "http://intervention-svc.bookflow.svc.cluster.local"

    redis_host: str
    redis_port: int = 6379

    auth_mode: str = "mock"
    log_level: str = "INFO"

    fan_in_timeout_seconds: float = 3.0


settings = Settings()
