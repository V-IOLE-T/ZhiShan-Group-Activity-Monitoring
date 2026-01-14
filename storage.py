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
    
    def get_record_by_user_month(self, user_id, month):
        """根据用户ID和月份查找记录"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/search"
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "用户ID",
                        "operator": "is",
                        "value": [user_id]
                    },
                    {
                        "field_name": "统计周期",
                        "operator": "is",
                        "value": [month]
                    }
                ]
            }
        }
        try:
            response = requests.post(
                url,
                headers=self.auth.get_headers(),
                json=payload,
                timeout=10
            )
            data = response.json()
            if data.get('code') != 0:
                print(f"  > [API] ⚠️  Bitable 搜索失败 (请检查是否已添加 '统计周期' 列): {data}")
                return None
            items = data.get('data', {}).get('items', [])
            if items:
                print(f"  > [API] ✅ 找到已存在的记录")
            else:
                print(f"  > [API] ℹ️  未找到记录，将创建新记录")
            return items[0] if items else None
        except requests.exceptions.Timeout:
            print(f"❌ 查找记录超时: 请求 Bitable API 超时")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 查找记录请求出错: {e}")
            return None
        except Exception as e:
            print(f"❌ 查找记录出错: {e}")
            return None

    def update_or_create_record(self, user_id, user_name, metrics_delta):
        """按月实时更新或创建记录"""
        month = datetime.now().strftime("%Y-%m")
        record = self.get_record_by_user_month(user_id, month)
        
        fields = {
            "用户ID": user_id,
            "用户名称": user_name,
            "人员": [{"id": user_id}],  # 人员字段，关联飞书账号
            "统计周期": month,
            "更新时间": int(datetime.now().timestamp() * 1000)
        }
        
        if record:
            record_id = record['record_id']
            old_fields = record['fields']
            # 在本月旧数据基础上累加
            fields.update({
                "发言次数": int(old_fields.get("发言次数", 0)) + metrics_delta.get("message_count", 0),
                "发言字数": int(old_fields.get("发言字数", 0)) + metrics_delta.get("char_count", 0),
                "被回复数": int(old_fields.get("被回复数", 0)) + metrics_delta.get("reply_received", 0),
                "单独被@次数": int(old_fields.get("单独被@次数", 0)) + metrics_delta.get("mention_received", 0),
                "发起话题数": int(old_fields.get("发起话题数", 0)) + metrics_delta.get("topic_initiated", 0),
                "点赞数": int(old_fields.get("点赞数", 0)) + metrics_delta.get("reaction_given", 0),
                "被点赞数": int(old_fields.get("被点赞数", 0)) + metrics_delta.get("reaction_received", 0),
            })
            # 重新计算分数
            score = (
                fields["发言次数"] * 1.0 +
                fields["发言字数"] * 0.01 +
                fields["被回复数"] * 1.5 +
                fields["单独被@次数"] * 1.5 +
                fields["发起话题数"] * 1.0 +
                fields["点赞数"] * 1.0 +
                fields["被点赞数"] * 1.0
            )
            fields["活跃度分数"] = round(score, 2)
            
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
            print(f"  > [API] 正在更新记录 {record_id}...")
            try:
                response = requests.put(url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10)
                result = response.json()
                if result.get('code') == 0:
                    print(f"  > [API] ✅ 更新成功")
                else:
                    print(f"  > [API] ❌ 更新失败: {result}")
                    print(f"  > [DEBUG] URL: {url}")
                    print(f"  > [DEBUG] Fields: {fields}")
                    raise Exception(f"Bitable API 返回错误: {result}")
            except requests.exceptions.Timeout:
                print(f"  > [API] ❌ 更新超时")
                raise
            except requests.exceptions.RequestException as e:
                print(f"  > [API] ❌ 请求异常: {e}")
                raise
        else:
            # 本月尚无记录，创建新行
            fields.update({
                "发言次数": metrics_delta.get("message_count", 0),
                "发言字数": metrics_delta.get("char_count", 0),
                "被回复数": metrics_delta.get("reply_received", 0),
                "单独被@次数": metrics_delta.get("mention_received", 0),
                "发起话题数": metrics_delta.get("topic_initiated", 0),
                "点赞数": metrics_delta.get("reaction_given", 0),
                "被点赞数": metrics_delta.get("reaction_received", 0),
            })
            score = (
                fields["发言次数"] * 1.0 +
                fields["发言字数"] * 0.01 +
                fields["被回复数"] * 1.5 +
                fields["单独被@次数"] * 1.5 +
                fields["发起话题数"] * 1.0 +
                fields["点赞数"] * 1.0 +
                fields["被点赞数"] * 1.0
            )
            fields["活跃度分数"] = round(score, 2)
            
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
            print(f"  > [API] 正在创建新记录...")
            try:
                response = requests.post(url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10)
                result = response.json()
                if result.get('code') == 0:
                    print(f"  > [API] ✅ 创建成功")
                else:
                    print(f"  > [API] ❌ 创建失败: {result}")
                    print(f"  > [DEBUG] URL: {url}")
                    print(f"  > [DEBUG] Fields: {fields}")
                    raise Exception(f"Bitable API 返回错误: {result}")
            except requests.exceptions.Timeout:
                print(f"  > [API] ❌ 创建超时")
                raise
            except requests.exceptions.RequestException as e:
                print(f"  > [API] ❌ 请求异常: {e}")
                raise
