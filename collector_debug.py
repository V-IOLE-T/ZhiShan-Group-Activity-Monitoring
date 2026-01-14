import requests
import time
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class MessageCollector:
    def __init__(self, auth):
        self.auth = auth
        self.chat_id = os.getenv('CHAT_ID')
    
    def get_messages(self, hours=1):
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        
        # 计算时间范围
        end_time = int(time.time() * 1000)
        start_time = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
        
        print(f"[DEBUG] 查询时间范围: {datetime.fromtimestamp(start_time/1000)} 到 {datetime.fromtimestamp(end_time/1000)}")
        
        all_messages = []
        page_token = None
        
        while True:
            params = {
                "container_id_type": "chat",
                "container_id": self.chat_id,
                "start_time": start_time,
                "end_time": end_time,
                "page_size": 50
            }
            
            if page_token:
                params['page_token'] = page_token
            
            response = requests.get(
                url, 
                headers=self.auth.get_headers(),
                params=params
            )
            data = response.json()
            
            print(f"[DEBUG] API 响应码: {data.get('code')}")
            
            if data.get('code') != 0:
                print(f"获取消息失败: {data}")
                break
            
            messages = data.get('data', {}).get('items', [])
            print(f"[DEBUG] 本次获取到 {len(messages)} 条消息")
            all_messages.extend(messages)
            
            if not data.get('data', {}).get('has_more'):
                break
            
            page_token = data.get('data', {}).get('page_token')
            time.sleep(0.1)
        
        print(f"采集到 {len(all_messages)} 条消息")
        return all_messages
