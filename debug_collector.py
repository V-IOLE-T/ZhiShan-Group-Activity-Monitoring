import requests
import os
import time
from datetime import datetime, timedelta
from auth import FeishuAuth
from dotenv import load_dotenv

load_dotenv()

def debug_messages():
    print("="*60)
    print("飞书消息采集诊断工具")
    print("="*60)
    
    # 1. 测试认证
    print("\n[步骤 1] 测试认证...")
    try:
        auth = FeishuAuth()
        token = auth.get_tenant_access_token()
        print(f"✅ 认证成功，Token 长度: {len(token)}")
    except Exception as e:
        print(f"❌ 认证失败: {e}")
        return
    
    # 2. 检查配置
    chat_id = os.getenv('CHAT_ID')
    print(f"\n[步骤 2] 检查配置...")
    print(f"CHAT_ID: {chat_id}")
    
    if not chat_id:
        print("❌ CHAT_ID 未配置！")
        return
    
    # 3. 测试获取群信息
    print(f"\n[步骤 3] 获取群聊信息...")
    chat_url = f"https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    chat_response = requests.get(chat_url, headers=headers, params={"user_id_type": "open_id"})
    chat_data = chat_response.json()
    
    if chat_data.get('code') == 0:
        chat_info = chat_data.get('data', {})
        print(f"✅ 群聊名称: {chat_info.get('name', '未知')}")
        print(f"   群聊类型: {chat_info.get('chat_mode', '未知')}")
        print(f"   成员数量: {chat_info.get('member_count', 0)}")
        
        # 检查是否是外部群
        if chat_info.get('chat_mode') == 'group':
            print("   ⚠️  这是一个普通群聊")
        else:
            print(f"   ⚠️  群聊模式: {chat_info.get('chat_mode')}")
    else:
        print(f"❌ 获取群信息失败: {chat_data}")
        if chat_data.get('code') == 230002:
            print("   提示: 机器人可能不在该群中")
        return
    
    # 4. 尝试不带时间限制获取消息
    print(f"\n[步骤 4] 尝试获取最新消息（不限时间）...")
    msg_url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = {
        "container_id_type": "chat",
        "container_id": chat_id,
        "page_size": 10
    }
    
    msg_response = requests.get(msg_url, headers=headers, params=params)
    msg_data = msg_response.json()
    
    if msg_data.get('code') == 0:
        messages = msg_data.get('data', {}).get('items', [])
        print(f"✅ 接口调用成功，返回消息数: {len(messages)}")
        
        if len(messages) == 0:
            print("\n⚠️  返回 0 条消息，可能的原因:")
            print("   1. 机器人进群后，群内还没有新消息")
            print("   2. 这是外部群，机器人无权读取消息")
            print("   3. 权限刚发布，还在同步中（等待1-2分钟）")
            print("\n建议操作:")
            print("   - 在群里发送一条测试消息")
            print("   - 等待30秒后重新运行此脚本")
        else:
            print("\n消息列表:")
            for i, m in enumerate(messages, 1):
                # 处理 sender.id 可能是字符串或字典的情况
                sender_info = m.get('sender', {})
                sender_id_obj = sender_info.get('id', {})
                
                if isinstance(sender_id_obj, dict):
                    sender_id = sender_id_obj.get('open_id', '未知')
                elif isinstance(sender_id_obj, str):
                    sender_id = sender_id_obj
                else:
                    sender_id = '未知'
                
                msg_type = m.get('msg_type', '未知')
                create_time = m.get('create_time', 0)
                
                # 转换时间戳
                if create_time:
                    try:
                        dt = datetime.fromtimestamp(int(create_time) / 1000)
                        time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        time_str = '时间解析失败'
                else:
                    time_str = '未知'
                
                print(f"\n   消息 {i}:")
                print(f"   - 发送人: {sender_id[:20] if len(sender_id) > 20 else sender_id}")
                print(f"   - 类型: {msg_type}")
                print(f"   - 时间: {time_str}")
                
                if msg_type == 'text':
                    content = m.get('body', {}).get('content', '')
                    print(f"   - 内容预览: {content[:80] if len(content) > 80 else content}...")
    else:
        print(f"❌ 获取消息失败: {msg_data}")
        error_code = msg_data.get('code')
        
        if error_code == 230002:
            print("   提示: 机器人不在该群中")
        elif error_code == 230027:
            print("   提示: 缺少权限 im:message.group_msg")
        elif error_code == 99991668:
            print("   提示: 外部群消息读取受限")
        
        return
    
    # 5. 测试带时间范围的查询
    print(f"\n[步骤 5] 测试带时间范围的查询（最近1小时）...")
    end_time = int(time.time() * 1000)
    start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    
    print(f"   开始时间: {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   结束时间: {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    
    params_with_time = {
        "container_id_type": "chat",
        "container_id": chat_id,
        "start_time": start_time,
        "end_time": end_time,
        "page_size": 50
    }
    
    time_response = requests.get(msg_url, headers=headers, params=params_with_time)
    time_data = time_response.json()
    
    if time_data.get('code') == 0:
        time_messages = time_data.get('data', {}).get('items', [])
        print(f"✅ 最近1小时消息数: {len(time_messages)}")
    else:
        print(f"❌ 带时间查询失败: {time_data}")
    
    print("\n" + "="*60)
    print("诊断完成！")
    print("="*60)

if __name__ == "__main__":
    debug_messages()
