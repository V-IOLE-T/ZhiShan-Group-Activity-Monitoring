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
        
        # 计算时间阈值（毫秒）
        time_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
        
        all_messages = []
        page_token = None
        
        while True:
            # 不使用 start_time 和 end_time，直接获取最新消息
            params = {
                "container_id_type": "chat",
                "container_id": self.chat_id,
                "page_size": 50
            }
            
            if page_token:
                params['page_token'] = page_token
            
            response = requests.get(
                url, 
                headers=self.auth.get_headers(),
                params=params,
                timeout=10
            )
            data = response.json()
            
            if data.get('code') != 0:
                print(f"获取消息失败: {data}")
                break
            
            messages = data.get('data', {}).get('items', [])
            
            # 在代码层面过滤时间范围
            for msg in messages:
                create_time = msg.get('create_time', 0)
                if isinstance(create_time, str):
                    create_time = int(create_time)
                
                # 只保留指定时间范围内的消息
                if create_time >= time_threshold:
                    all_messages.append(msg)
            
            # 如果没有更多消息，或者已经获取到足够旧的消息，停止翻页
            if not data.get('data', {}).get('has_more'):
                break
            
            # 检查最后一条消息是否已经超出时间范围
            if messages:
                last_msg_time = messages[-1].get('create_time', 0)
                if isinstance(last_msg_time, str):
                    last_msg_time = int(last_msg_time)
                if last_msg_time < time_threshold:
                    break
            
            page_token = data.get('data', {}).get('page_token')
            time.sleep(0.1)
        
        print(f"采集到 {len(all_messages)} 条消息")
        return all_messages

    def get_user_names(self, user_ids):
        """获取群聊成员在群里的昵称（备注）"""
        if not user_ids:
            return {}
        
        url = f"https://open.feishu.cn/open-apis/im/v1/chats/{self.chat_id}/members"
        user_names = {}
        page_token = None
        
        print("正在获取群成员备注...")
        
        while True:
            params = {
                "member_id_type": "open_id",
                "page_size": 100
            }
            if page_token:
                params["page_token"] = page_token
                
            try:
                response = requests.get(
                    url,
                    headers=self.auth.get_headers(),
                    params=params,
                    timeout=10
                )
                data = response.json()
                
                if data.get('code') == 0:
                    data_obj = data.get('data') or {}
                    items = data_obj.get('items') or []
                    for member in items:
                        # 优先使用在群里的备注名 (name)，如果没有则使用真实姓名
                        user_names[member.get('member_id')] = member.get('name', '')
                    
                    if not data_obj.get('has_more'):
                        break
                    page_token = data_obj.get('page_token')
                else:
                    print(f"获取群成员列表失败: {data}")
                    break
            except Exception as e:
                print(f"请求群成员信息出错: {e}")
                break
        
        return user_names

    def get_message_sender(self, message_id):
        """获取指定消息的发送者 ID"""
        if not message_id:
            return None
            
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        try:
            response = requests.get(
                url,
                headers=self.auth.get_headers(),
                timeout=10
            )
            data = response.json()
            if data.get('code') == 0:
                data_obj = data.get('data') or {}
                items = data_obj.get('items') or []
                if not items:
                    print(f"未找到消息 {message_id} 的详情")
                    return None
                    
                sender = items[0].get('sender', {})
                sender_id_obj = sender.get('id', {})
                if isinstance(sender_id_obj, dict):
                    return sender_id_obj.get('open_id')
                return sender_id_obj
            else:
                print(f"获取消息详情失败: {data}")
        except Exception as e:
            print(f"请求消息详情出错: {e}")
        return None

