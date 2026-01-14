import requests
import os
from auth import FeishuAuth
from dotenv import load_dotenv

load_dotenv()

def list_bot_chats():
    print("正在获取机器人所在的群聊列表...")
    try:
        auth = FeishuAuth()
        token = auth.get_tenant_access_token()
        
        url = "https://open.feishu.cn/open-apis/im/v1/chats"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get('code') == 0:
            items = data.get('data', {}).get('items', [])
            if not items:
                print("❌ 机器人目前没有加入任何群聊。请前往飞书群设置 -> 群机器人 -> 添加机器人。")
            else:
                print(f"✅ 成功找到 {len(items)} 个群聊:")
                print("-" * 40)
                for chat in items:
                    print(f"群名称: {chat.get('name')}")
                    print(f"CHAT_ID (填入.env): {chat.get('chat_id')}")
                    print("-" * 40)
        else:
            print(f"❌ 获取列表失败: {data}")
            
    except Exception as e:
        print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    list_bot_chats()
