"""
Web后端配置管理
"""
import sys
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app_paths import default_static_dir, default_upload_temp_dir


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
    # 绝对路径：打包后 CWD 不再是项目目录，相对路径会解析到错误位置。
    upload_temp_dir: str = Field(default_factory=lambda: str(default_upload_temp_dir()))
    
    ws_ping_interval: int = Field(default=20)
    ws_ping_timeout: int = Field(default=10)
    
    static_dir: str = Field(default_factory=lambda: str(default_static_dir()))

    # Pydantic v2 风格的配置（旧的 class Config 已弃用）
    model_config = SettingsConfigDict(
        env_prefix="PUMC_",
        env_file=".env",
        extra="ignore",
    )


settings = WebBackendSettings()
