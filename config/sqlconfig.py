from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os




class SQLSETTINGS(BaseSettings):
    
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    
sqlsettings = SQLSETTINGS() #type: ignore



class MODELCONFIG(BaseSettings):
    
    MODEL_NAME: str = "gpt-5.2"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: str
    TEMPERATURE: float = 0.0
    
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


modelconfig = MODELCONFIG() #type: ignore