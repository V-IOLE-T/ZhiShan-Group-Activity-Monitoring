import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class FeishuAuth:
    def __init__(self):
        self.app_id = os.getenv('APP_ID')
        self.app_secret = os.getenv('APP_SECRET')
        self.tenant_access_token = None
        self.token_expire_time = 0
        
        # 验证环境变量
        if not self.app_id or not self.app_secret:
            raise ValueError("❌ APP_ID和APP_SECRET必须在.env文件中配置")
    
    def get_tenant_access_token(self, force_refresh=False):
        """获取tenant_access_token，支持自动刷新"""
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
                print(f"✅ Token获取成功，有效期至 {datetime.fromtimestamp(self.token_expire_time).strftime('%H:%M:%S')}")
                return self.tenant_access_token
            else:
                raise Exception(f"获取token失败: code={data.get('code')}, msg={data.get('msg')}")
        except requests.exceptions.Timeout:
            raise Exception("获取token超时，请检查网络连接")
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取token请求失败: {e}")
    
    def get_headers(self):
        """获取API请求头，自动刷新token"""
        if not self.tenant_access_token or datetime.now().timestamp() >= self.token_expire_time:
            self.get_tenant_access_token(force_refresh=True)
        
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
