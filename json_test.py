from auth import FeishuAuth
from collector import MessageCollector
from calculator import MetricsCalculator
import json

# 1. 认证
auth = FeishuAuth()
auth.get_tenant_access_token()

# 2. 采集
collector = MessageCollector(auth)
messages = collector.get_messages(hours=48)

# 3. 计算
result = {
    "message_count": len(messages),
    "users": []
}

if messages:
    calculator = MetricsCalculator(messages)
    metrics = calculator.calculate()
    
    sorted_users = sorted(metrics.items(), key=lambda x: x[1]['score'], reverse=True)
    for uid, data in sorted_users:
        result["users"].append({
            "user_id": uid,
            "user_name": data['user_name'],
            "score": data['score'],
            "message_count": data['message_count']
        })

# 输出 JSON
with open('test_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Results saved to test_result.json")
print(f"Total messages: {result['message_count']}")
print(f"Total users: {len(result['users'])}")
