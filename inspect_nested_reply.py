import os
import requests
import json
from dotenv import load_dotenv
from auth import FeishuAuth

load_dotenv()

def inspect_message(message_id):
    auth = FeishuAuth()
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
    
    print(f"正在查询消息: {message_id} ...")
    response = requests.get(
        url,
        headers=auth.get_headers()
    )
    data = response.json()
    
    print("\n--- 原始 JSON 响应 ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    # 将完整的 JSON 写入文件以便读取
    with open("debug_message.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\n✅ 完整响应已保存到 debug_message.json")
    
    if data.get('code') == 0:
        items = data.get('data', {}).get('items') or []
        if items:
            msg = items[0]
            print("\n--- 关键字段提取 ---")
            for key, value in msg.items():
                if key != 'body': # body is redundant with items
                    print(f"{key}: {value}")
            
            # 尝试解析 content 字符串
            try:
                content = json.loads(msg.get('content', '{}'))
                print("\n--- 解析后的内容 (content) ---")
                print(json.dumps(content, indent=2, ensure_ascii=False))
            except:
                print(f"\n无法解析内容: {msg.get('content')}")
        else:
            print("未找到消息内容")
    else:
        print(f"查询失败: {data}")

if __name__ == "__main__":
    # 使用之前发现的 root_id
    msg_id = "om_x100b594194e7aca4c44a19b89764960"
    inspect_message(msg_id)
