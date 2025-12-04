"""
配置管理模块
从环境变量加载LLM配置
数据库配置统一使用 backend.database.db_config
"""
import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装dotenv，直接使用环境变量


class Config:
    """LLM配置类（数据库配置使用backend.database.db_config）"""
    
    def __init__(
        self,
        API_KEY: Optional[str] = None,
        BASE_URL: Optional[str] = None,
        MODEL_NAME: Optional[str] = None,
        MAX_RETRY: Optional[int] = None,
        TIMEOUT: Optional[int] = None
    ):
        # LLM配置
        self.API_KEY = API_KEY
        self.BASE_URL = BASE_URL
        self.MODEL_NAME = MODEL_NAME
        self.MAX_RETRY = MAX_RETRY or 3
        self.TIMEOUT = TIMEOUT or 60
    
    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        return cls(
            API_KEY=os.getenv("DASHSCOPE_API_KEY"),
            BASE_URL=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            MODEL_NAME=os.getenv("MODEL_NAME", "qwen-plus"),
            MAX_RETRY=int(os.getenv("MAX_RETRY", "3")),
            TIMEOUT=int(os.getenv("LLM_TIMEOUT", "60"))
        )
