from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./splituz.db"
    dataset_dir: Path = Path("dataset")
    result_dir: Path = Path("natija")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

