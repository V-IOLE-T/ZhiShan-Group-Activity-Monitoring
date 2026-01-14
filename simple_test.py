from auth import FeishuAuth
from collector import MessageCollector
from calculator import MetricsCalculator

print("="*50)
print("简化测试")
print("="*50)

# 1. 认证
auth = FeishuAuth()
auth.get_tenant_access_token()
print("✅ 认证成功")

# 2. 采集
collector = MessageCollector(auth)
messages = collector.get_messages(hours=48)
print(f"✅ 采集到 {len(messages)} 条消息")

# 3. 计算
if messages:
    calculator = MetricsCalculator(messages)
    metrics = calculator.calculate()
    print(f"✅ 计算完成，共 {len(metrics)} 位用户")
    
    # 显示前3名
    sorted_users = sorted(metrics.items(), key=lambda x: x[1]['score'], reverse=True)[:3]
    print("\n活跃度 Top3:")
    for rank, (uid, data) in enumerate(sorted_users, 1):
        print(f"{rank}. {data['user_name']} - {data['score']}分")
else:
    print("⚠️ 无消息")

print("\n" + "="*50)
print("测试完成")
