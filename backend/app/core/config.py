import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "Almeno Transaction Intelligence Platform"
    API_V1_STR: str = "/api/v1"

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "transaction_intelligence"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: str = "6379"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    # Gemini LLM Config
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Anomaly Detection Configurations
    ANOMALY_Z_SCORE_THRESHOLD: float = 3.0
    ANOMALY_MEDIAN_MULTIPLIER: float = 3.0
    RAPID_TRANSACTION_WINDOW_MINUTES: int = 10
    
    # Comma-separated domestic brands for checking USD usage anomaly
    DOMESTIC_BRANDS_RAW: str = "Flipkart,Swiggy,Zomato,Jio Recharge,HDFC ATM,IRCTC,MakeMyTrip,Ola,BookMyShow"

    @property
    def DOMESTIC_BRANDS(self) -> List[str]:
        return [brand.strip().lower() for brand in self.DOMESTIC_BRANDS_RAW.split(",") if brand.strip()]

    # Security & limits
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: List[str] = ["csv"]


settings = Settings()
