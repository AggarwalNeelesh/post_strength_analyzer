import os
import re
from typing import Optional, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")
    
    # MySQL Database Settings
    MYSQL_HOST: str
    MYSQL_PORT: int = Field(default=3306)
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str
    MYSQL_POOL_SIZE: int = Field(default=5)
    MYSQL_POOL_NAME: str = Field(default="mypool")
    
    # LLM Provider Configuration
    LLM_PROVIDER: Literal["openai", "groq"] = Field(default="openai")
    
    # OpenAI Settings
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = Field(default="gpt-3.5-turbo")
    
    # Groq Settings
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = Field(default="llama2-70b-4096")
    
    # Add this validator to clean up the LLM_PROVIDER value
    @field_validator('LLM_PROVIDER', mode='before')
    @classmethod
    def clean_llm_provider(cls, v):
        if isinstance(v, str):
            # Remove comments and whitespace
            v = re.sub(r'\s*#.*$', '', v).strip()
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings() 