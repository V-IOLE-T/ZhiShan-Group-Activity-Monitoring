from auth import FeishuAuth
from collector_debug import MessageCollector

def quick_test():
    print("快速测试 - 带调试信息")
    print("="*50)
    
    auth = FeishuAuth()
    auth.get_tenant_access_token()
    
    collector = MessageCollector(auth)
    messages = collector.get_messages(hours=48)
    
    print(f"\n最终结果: {len(messages)} 条消息")
    
    if messages:
        print("\n消息类型统计:")
        msg_types = {}
        for m in messages:
            msg_type = m.get('msg_type', 'unknown')
            msg_types[msg_type] = msg_types.get(msg_type, 0) + 1
        
        for msg_type, count in msg_types.items():
            print(f"  {msg_type}: {count} 条")

if __name__ == "__main__":
    quick_test()
