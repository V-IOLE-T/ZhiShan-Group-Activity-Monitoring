"""
飞书API认证模块

提供飞书tenant_access_token的获取和自动刷新功能
"""
import requests
import os
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv
from logger import get_logger

load_dotenv()

# 初始化日志记录器
logger = get_logger(__name__)


class FeishuAuth:
    """
    飞书API认证管理类

    负责获取和管理tenant_access_token，支持自动刷新

    Attributes:
        app_id: 飞书应用ID
        app_secret: 飞书应用密钥
        tenant_access_token: 当前有效的访问令牌
        token_expire_time: 令牌过期时间戳（秒）

    Example:
        >>> auth = FeishuAuth()
        >>> token = auth.get_tenant_access_token()
        >>> headers = auth.get_headers()
    """

    def __init__(self) -> None:
        """
        初始化认证管理器

        从环境变量读取APP_ID和APP_SECRET

        Raises:
            ValueError: 当APP_ID或APP_SECRET未配置时
        """
        self.app_id: Optional[str] = os.getenv('APP_ID')
        self.app_secret: Optional[str] = os.getenv('APP_SECRET')
        self.tenant_access_token: Optional[str] = None
        self.token_expire_time: float = 0

        # 验证环境变量
        if not self.app_id or not self.app_secret:
            error_msg = "APP_ID和APP_SECRET必须在.env文件中配置"
            logger.error(f"❌ {error_msg}")
            raise ValueError(f"❌ {error_msg}")

    def get_tenant_access_token(self, force_refresh: bool = False) -> str:
        """
        获取tenant_access_token，支持自动刷新

        检查token是否有效，如果已过期或即将过期（提前5分钟），
        则自动刷新token

        Args:
            force_refresh: 是否强制刷新token，默认False

        Returns:
            有效的tenant_access_token字符串

        Raises:
            Exception: 当token获取失败时

        Example:
            >>> auth = FeishuAuth()
            >>> token = auth.get_tenant_access_token()
            >>> # 强制刷新
            >>> token = auth.get_tenant_access_token(force_refresh=True)
        """
        # 检查token是否still有效（提前5分钟刷新）
        if not force_refresh and self.tenant_access_token:
            if datetime.now().timestamp() < self.token_expire_time:
                return self.tenant_access_token
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if data.get('code') == 0:
                self.tenant_access_token = data['tenant_access_token']
                # 设置过期时间（API返回的expire字段，默认7200秒，提前5分钟刷新）
                expire_in = data.get('expire', 7200) - 300
                self.token_expire_time = datetime.now().timestamp() + expire_in
                expire_time_str = datetime.fromtimestamp(self.token_expire_time).strftime('%H:%M:%S')
                logger.info(f"✅ Token获取成功，有效期至 {expire_time_str}")
                return self.tenant_access_token
            else:
                error_msg = f"获取token失败: code={data.get('code')}, msg={data.get('msg')}"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except requests.exceptions.Timeout:
            error_msg = "获取token超时，请检查网络连接"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"获取token请求失败: {e}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def get_headers(self) -> Dict[str, str]:
        """
        获取飞书API请求头，自动刷新token

        返回包含Authorization和Content-Type的请求头字典
        如果token已过期，自动刷新

        Returns:
            包含认证信息的请求头字典

        Example:
            >>> auth = FeishuAuth()
            >>> headers = auth.get_headers()
            >>> response = requests.get(url, headers=headers)
        """
        if not self.tenant_access_token or datetime.now().timestamp() >= self.token_expire_time:
            self.get_tenant_access_token(force_refresh=True)
        
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
