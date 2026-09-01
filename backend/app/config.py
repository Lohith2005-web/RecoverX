import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "RecoverX — AI Revenue Recovery Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./recoverx.db")
    
    # Simulator Defaults
    SEED: int = 42
    DEFAULT_NUM_TRANSACTIONS: int = 50000
    
    # Autonomy Thresholds
    AUTO_EXECUTE_CONFIDENCE: float = 0.90
    APPROVAL_CONFIDENCE: float = 0.70

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
