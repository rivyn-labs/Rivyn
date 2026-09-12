import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI-Powered Observability Platform"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # AI / Reasoning
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anomaly_threshold: float = 0.55
    sliding_window_sec: int = 60
    max_incident_candidates: int = 15

    # Storage paths
    data_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    samples_dir: str = os.path.join(data_dir, "samples")

settings = Settings()
