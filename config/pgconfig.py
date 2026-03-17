from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os



class PGSETTINGS(BaseSettings):
    PGHOST: str
    PGPORT: int
    PGUSER: str
    PGPASSWORD: str
    PGDATABASE: str
    
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    
pgsettings = PGSETTINGS() #type: ignore