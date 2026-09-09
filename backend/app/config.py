"""CYBERPULSE AI — application configuration (env-driven)."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> str:
    # backend/app/config.py -> backend/app -> backend -> project root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # paths
    project_root: str = _project_root()
    data_dir: str = ""
    artifacts_dir: str = ""

    # database
    database_url: str = ""
    db_echo: bool = False

    # neo4j / redis (optional)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    redis_url: str = "redis://localhost:6379/0"

    # auth
    jwt_secret: str = "change-me-in-production-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ml
    model_path: str = ""
    model_registry_path: str = ""

    # risk engine
    risk_weight_ml: float = 0.40
    risk_weight_anomaly: float = 0.20
    risk_weight_graph: float = 0.15
    risk_weight_temporal: float = 0.15
    risk_weight_history: float = 0.10
    risk_boost_factor: float = 0.20
    risk_alert_threshold: float = 60.0

    # api
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def database_url_resolved(self) -> str:
        url = self.database_url or f"sqlite:///{os.path.join(self.project_root, 'data', 'demo', 'cyberpulse.db')}"
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            path = url[len("sqlite:///"):]
            if not os.path.isabs(path):
                path = os.path.join(self.project_root, path)
                os.makedirs(os.path.dirname(path), exist_ok=True)
            url = f"sqlite:///{path}"
        return url

    @property
    def data_dir_resolved(self) -> str:
        return self.data_dir or os.path.join(self.project_root, "data")

    @property
    def artifacts_dir_resolved(self) -> str:
        return self.artifacts_dir or os.path.join(self.project_root, "ml", "artifacts")

    @property
    def model_path_resolved(self) -> str:
        return self.model_path or os.path.join(self.artifacts_dir_resolved, "model_v1.joblib")

    @property
    def model_registry_path_resolved(self) -> str:
        return self.model_registry_path or os.path.join(self.artifacts_dir_resolved, "model_registry.json")

    @property
    def risk_weights(self) -> dict:
        # Contextual signal weights (normalized to sum 1). The ML probability
        # is the risk anchor and is not part of this dict.
        return {
            "anomaly": self.risk_weight_anomaly,
            "graph": self.risk_weight_graph,
            "temporal": self.risk_weight_temporal,
            "history": self.risk_weight_history,
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()