from auth import FeishuAuth
from collector import MessageCollector
from calculator import MetricsCalculator

def test_auth():
    print("测试1: 飞书认证")
    try:
        auth = FeishuAuth()
        token = auth.get_tenant_access_token()
        print(f"✅ 认证成功，token长度: {len(token)}")
        return True
    except Exception as e:
        print(f"❌ 认证失败: {e}")
        return False

def test_collector():
    print("\n测试2: 消息采集")
    try:
        auth = FeishuAuth()
        auth.get_tenant_access_token()
        collector = MessageCollector(auth)
        messages = collector.get_messages(hours=48)  # 修改为48小时以获取更多历史消息
        print(f"✅ 成功采集 {len(messages)} 条消息")
        return messages
    except Exception as e:
        print(f"❌ 采集失败: {e}")
        return None

def test_calculator(messages):
    print("\n测试3: 指标计算")
    try:
        if not messages:
            print("⚠️  无消息数据，跳过计算测试")
            return None
        
        calculator = MetricsCalculator(messages)
        metrics = calculator.calculate()
        print(f"✅ 计算完成，共 {len(metrics)} 位用户")
        
        sorted_users = sorted(metrics.items(), key=lambda x: x[1]['score'], reverse=True)[:3]
        print("\n活跃度Top3:")
        for rank, (user_id, data) in enumerate(sorted_users, 1):
            print(f"{rank}. {data['user_name'][:15]} - {data['score']}分")
        
        return metrics
    except Exception as e:
        print(f"❌ 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("="*50)
    print("飞书活跃度监测系统 - 测试脚本")
    print("="*50)
    
    auth_ok = test_auth()
    if not auth_ok:
        print("\n请检查 .env 文件中的 APP_ID 和 APP_SECRET 配置")
        exit(1)
    
    messages = test_collector()
    if messages is None:
        print("\n请检查 .env 文件中的 CHAT_ID 配置")
        exit(1)
    
    metrics = test_calculator(messages)
    
    print("\n" + "="*50)
    print("测试完成！")
    print("="*50)
