import requests
import os
from dotenv import load_dotenv

load_dotenv()

class FeishuAuth:
    def __init__(self):
        self.app_id = os.getenv('APP_ID')
        self.app_secret = os.getenv('APP_SECRET')
        self.tenant_access_token = None
    
    def get_tenant_access_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        response = requests.post(url, json=payload)
        data = response.json()
        
        if data.get('code') == 0:
            self.tenant_access_token = data['tenant_access_token']
            return self.tenant_access_token
        else:
            raise Exception(f"获取token失败: {data}")
    
    def get_headers(self):
        if not self.tenant_access_token:
            self.get_tenant_access_token()
        
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
