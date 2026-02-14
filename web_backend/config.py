"""
Web后端配置管理
"""
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class WebBackendSettings(BaseSettings):
    """Web后端配置"""
    
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)
    
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: List[str] = Field(default=["*"])
    cors_allow_headers: List[str] = Field(default=["*"])
    
    max_upload_size: int = Field(default=10 * 1024 * 1024)
    upload_temp_dir: str = Field(default="./temp/uploads")
    
    ws_ping_interval: int = Field(default=20)
    ws_ping_timeout: int = Field(default=10)
    
    static_dir: str = Field(default="./web/dist")
    
    class Config:
        env_prefix = "PUMC_"
        env_file = ".env"


settings = WebBackendSettings()
