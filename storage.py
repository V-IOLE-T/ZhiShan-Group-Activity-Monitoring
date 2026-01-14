import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class BitableStorage:
    def __init__(self, auth):
        self.auth = auth
        self.app_token = os.getenv('BITABLE_APP_TOKEN')
        self.table_id = os.getenv('BITABLE_TABLE_ID')
    
    def save_metrics(self, metrics):
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_create"
        
        records = []
        for user_id, data in metrics.items():
            records.append({
                "fields": {
                    "用户ID": data['user_id'],
                    "用户名称": data['user_name'],
                    "发言次数": data['message_count'],
                    "发言字数": data['char_count'],
                    "被回复数": data['reply_received'],
                    "被@次数": data['mention_received'],
                    "发起话题数": data['topic_initiated'],
                    "活跃度分数": data['score'],
                    # 飞书多维表格日期字段要求毫秒级时间戳
                    "更新时间": int(datetime.now().timestamp() * 1000)
                }
            })
        
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            payload = {"records": batch}
            
            response = requests.post(
                url,
                headers=self.auth.get_headers(),
                json=payload
            )
            
            result = response.json()
            if result.get('code') == 0:
                print(f"成功写入 {len(batch)} 条记录")
            else:
                print(f"写入失败: {result}")
            
            time.sleep(0.5)
